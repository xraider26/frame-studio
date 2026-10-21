import copy
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .assets import checked_file
from .store import Store, StudioError
from .templates import DEFAULT_SETTINGS, STEPS, TEMPLATES
from .generators import VIDEO_PROFILES, IMAGE_PROFILES, prompt_for, validate_template
from .exports import export_project
from .creative import default_production, Direction, Production, merge, validated, normalize_direction


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def event(p, kind, actor, message):
    p['history'].append({'at': now(), 'type': kind, 'actor': actor[:100], 'message': message[:1000]})


def clean_text(value, limit=12000):
    if not isinstance(value, str) or len(value) > limit:
        raise StudioError('invalid_input', f'Text must be a string of at most {limit} characters.')
    return value.strip()


class Studio(Store):
    def __init__(self, db_path, media_root, inbox):
        super().__init__(db_path)
        self.media_root, self.inbox = Path(media_root).resolve(), Path(inbox).resolve()
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.inbox.mkdir(parents=True, exist_ok=True)

    def create_project(self, name, template_id, request_id=None, actor='user'):
        if request_id:
            for p in self.all():
                if p.get('request_id') == request_id:
                    return p
        template = next((t for t in TEMPLATES if t['id'] == template_id), None)
        if not template or not clean_text(name, 150):
            raise StudioError('invalid_input', 'Choose a valid template and project name.')
        p = {'id': uid(), 'name': name.strip(), 'template_id': template_id, 'revision': 1, 'schema_version': 2,
             'created_at': now(), 'request_id': request_id, 'epoch': 1,
             'settings': dict(DEFAULT_SETTINGS, aspect_ratio=template['aspect']), 'documents': {},
             'approval_policy': {s: True for s in STEPS},
             'steps': {s: {'ready': False, 'status': 'draft'} for s in STEPS},
             'shots': [{'id': uid(), 'title': title, 'image_prompt': '', 'motion_prompt': '', 'narration': '', 'duration_seconds': 4, 'image_asset': None, 'video_asset': None} for title in template['structure']],
             'assets': [], 'jobs': [], 'history': [], 'production': default_production(template_id)}
        for shot in p['shots']:
            shot.update(direction=Direction().model_dump(), edit_duration_seconds=shot['duration_seconds'])
        event(p, 'created', actor, 'Project created from ' + template['name'])
        return self.insert(p)

    def list_projects(self):
        return [{k: p[k] for k in ['id', 'name', 'template_id', 'revision', 'created_at']} for p in self.all() if not p.get('deleted_at')]

    def list_deleted(self):
        return [{k: p[k] for k in ['id', 'name', 'template_id', 'revision', 'deleted_at']} for p in self.all() if p.get('deleted_at')]

    def delete_project(self, project_id, expected_revision):
        def update(p):
            if any(j['status'] == 'running' for j in p['jobs']):
                raise StudioError('job_running', 'Wait for the API job to finish before moving this project to Trash.', 409)
            p['deleted_at'] = now()
            for j in p['jobs']:
                if j['status'] in ['awaiting_external_output', 'queued']:
                    j['status'] = 'canceled'
            event(p, 'project_deleted', 'user', 'Moved to Trash; files preserved and project can be restored')
        return self.mutate(project_id, expected_revision, update)

    def restore_project(self, project_id):
        def update(p):
            p.pop('deleted_at', None)
            event(p, 'project_restored', 'user', 'Restored from Trash')
        return self.mutate(project_id, None, update, allow_deleted=True)

    def duplicate_project(self, project_id, name, actor):
        original = self.get(project_id)
        p = self.create_project(name or original['name'] + ' (copy)', original['template_id'], actor=actor)
        def update(clone):
            clone['settings'] = copy.deepcopy(original['settings'])
            clone['production'] = copy.deepcopy(original['production'])
            clone['documents'] = {k: copy.deepcopy(v) for k, v in original['documents'].items() if k in ['brief', 'script']}
            clone['shots'] = [{**copy.deepcopy(s), 'id': uid(), 'image_asset': None, 'video_asset': None} for s in original['shots']]
            for a in original['assets']:
                if a.get('role') != 'reference': continue
                source = Path(a['path']).resolve()
                if not source.is_relative_to(self.media_root) or not source.is_file(): continue
                asset_id = uid()
                dest = self.media_root / clone['id'] / (asset_id + source.suffix)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                clone['assets'].append({**copy.deepcopy(a), 'id': asset_id, 'path': str(dest), 'url': f'/api/studio/media/{clone["id"]}/{dest.name}', 'stale': False})
            for step in ['brief', 'script']:
                clone['steps'][step]['ready'] = bool(clone['documents'].get(step, {}).get('text'))
            self._progress(clone)
            event(clone, 'project_duplicated', actor, 'Plan and references copied; approvals, output takes and jobs start fresh')
        return self.mutate(p['id'], p['revision'], update)

    def export_handoff(self, project_id):
        return export_project(self, self.get(project_id))

    def get_project(self, project_id):
        p = self.get(project_id)
        p['next_action'] = self._next(p)
        return p

    def _progress(self, p):
        if p['shots'] and all(s['image_asset'] for s in p['shots']):
            p['steps']['visual_direction']['ready'] = True
        if p['shots'] and p['shots'][0]['video_asset']:
            p['steps']['pilot']['ready'] = True
        if p['shots'] and all(s['video_asset'] for s in p['shots']):
            p['steps']['production']['ready'] = True
        for step in STEPS:
            state = p['steps'][step]
            if not state['ready']:
                break
            if p['approval_policy'][step]:
                if state['status'] != 'approved':
                    state['status'] = 'awaiting_review'
                    break
            elif state['status'] not in ['approved', 'auto_proceeded']:
                state['status'] = 'auto_proceeded'
                event(p, 'auto_proceeded', 'studio', step.replace('_', ' ') + ' completed without human review (your policy)')

    def _next(self, p):
        for step in STEPS:
            state = p['steps'][step]
            if state['status'] in ['approved', 'auto_proceeded']:
                continue
            if state['ready']:
                return {'action': 'await_approval', 'step': step, 'message': 'Waiting for your review in the studio.'}
            if step in ['visual_direction', 'pilot', 'production']:
                kind = 'image' if step == 'visual_direction' else 'video'
                shots = p['shots'][:1] if step == 'pilot' else p['shots']
                shot = next((s for s in shots if not s[kind + '_asset']), None)
                if not shot:
                    return {'action': 'prepare_shots', 'step': step, 'message': 'Add shots to continue.'}
                if not shot['image_prompt' if kind == 'image' else 'motion_prompt'].strip():
                    return {'action': 'write_prompt', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': f"Prepare the {kind} prompt for {shot['title']}."}
                return {'action': 'generate', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': f"Generate {kind} for {shot['title']}."}
            return {'action': 'prepare_step', 'step': step, 'message': 'Prepare ' + step.replace('_', ' ') + '.'}
        return {'action': 'complete', 'step': None, 'message': 'All workflow steps complete.'}

    def next_action(self, project_id):
        return self._next(self.get(project_id))

    def _invalidate(self, p, step):
        for s in STEPS[STEPS.index(step):]:
            p['steps'][s] = {'ready': False, 'status': 'draft'}
        if STEPS.index(step) <= STEPS.index('visual_direction'):
            p['epoch'] += 1
            for shot in p['shots']:
                shot['image_asset'] = shot['video_asset'] = None
            for asset in p['assets']:
                asset['stale'] = True
        elif step in ['pilot', 'production']:
            p['video_epoch'] = p.get('video_epoch', 0) + 1
            # A rejected motion take must not immediately satisfy the step again.
            for shot in p['shots']:
                shot['video_asset'] = None
            for asset in p['assets']:
                if asset['kind'] in ['video', 'final_video']:
                    asset['stale'] = True
        if step != 'final_review':
            for asset in p['assets']:
                if asset['kind'] == 'final_video':
                    asset['stale'] = True
        for job in p['jobs']:
            if job['status'] in ['awaiting_external_output', 'queued']:
                job['status'] = 'superseded'

    def set_policy(self, project_id, policy, expected_revision):
        if not isinstance(policy, dict) or any(k not in STEPS or type(v) is not bool for k, v in policy.items()):
            raise StudioError('invalid_policy', 'Approval policy must map valid step names to true or false.')
        def update(p):
            for step, enabled in policy.items():
                if enabled and not p['approval_policy'][step] and p['steps'][step]['status'] == 'auto_proceeded':
                    for later in STEPS[STEPS.index(step):]:
                        p['steps'][later]['status'] = 'draft'
                p['approval_policy'][step] = enabled
            self._progress(p)
            event(p, 'policy_changed', 'user', 'Approval settings updated')
        return self.mutate(project_id, expected_revision, update)

    def complete_step(self, project_id, step, output, expected_revision, actor):
        if step not in ['brief', 'script', 'editor_handoff', 'final_review']:
            raise StudioError('invalid_step', 'This step requires returned image/video jobs, not a text completion.')
        text = clean_text(output.get('text', ''))
        if not text:
            raise StudioError('missing_output', 'Provide the actual step document or editing notes.')
        def update(p):
            if any(p['steps'][s]['status'] not in ['approved', 'auto_proceeded'] for s in STEPS[:STEPS.index(step)]):
                raise StudioError('step_blocked', 'Complete earlier workflow steps first.', 409)
            if step == 'final_review' and not output.get('export_asset_id'):
                raise StudioError('missing_export', 'Import the actual external edit as a final video before completing final review.')
            if step == 'final_review' and not any(a['id'] == output['export_asset_id'] and a['kind'] == 'final_video' and not a['stale'] for a in p['assets']):
                raise StudioError('invalid_export', 'Final export is not attached to this project.')
            if p['steps'][step]['ready']:
                self._invalidate(p, step)
            p['documents'][step] = {'text': text, **({'export_asset_id': output['export_asset_id']} if step == 'final_review' else {})}
            p['steps'][step] = {'ready': True, 'status': 'draft'}
            self._progress(p)
            event(p, 'step_prepared', actor, step.replace('_', ' ') + ' prepared')
        return self.mutate(project_id, expected_revision, update)

    def update_settings(self, project_id, settings, expected_revision, actor):
        if not isinstance(settings, dict) or any(k not in DEFAULT_SETTINGS for k in settings):
            raise StudioError('invalid_settings', 'Unknown creative setting.')
        for k, v in settings.items():
            if k == 'duration_seconds':
                if type(v) is not int or not 1 <= v <= 3600:
                    raise StudioError('invalid_settings', 'Duration must be 1–3600 seconds.')
            else:
                clean_text(v, 3000)
        if 'aspect_ratio' in settings and settings['aspect_ratio'] not in ['16:9', '9:16', '1:1']:
            raise StudioError('invalid_settings', 'Choose 16:9, 9:16 or 1:1.')
        for field, profiles in [('video_generator', VIDEO_PROFILES), ('image_generator', IMAGE_PROFILES)]:
            if field in settings and settings[field] not in [v['id'] for v in profiles]:
                raise StudioError('invalid_generator', 'Choose a supported generator profile or Custom.')
        if 'generation_mode' in settings and settings['generation_mode'] not in ['external_agent', 'api']:
            raise StudioError('invalid_mode', 'Choose external_agent or api execution.')
        for field in ['custom_video_template', 'custom_image_template']:
            if field in settings: validate_template(settings[field])
        def update(p):
            if any(p['settings'][k] != v for k, v in settings.items()):
                self._invalidate(p, 'visual_direction')
                p['settings'].update(settings)
                event(p, 'settings_changed', actor, 'Creative settings updated; dependent outputs require review')
        return self.mutate(project_id, expected_revision, update)

    def update_production(self, project_id, production, expected_revision, actor):
        if not isinstance(production, dict):
            raise StudioError('invalid_creative_record', 'Production must be an object.')
        def update(p):
            data = validated(Production, merge(p['production'], production))
            ids = [e['id'] for e in data['bible']]
            if len(ids) != len(set(ids)) or any(not key for key in ids):
                raise StudioError('invalid_creative_record', 'Bible entities need distinct nonempty IDs.')
            if data != p['production']:
                self._invalidate(p, 'visual_direction')
                p['production'] = data
                event(p, 'production_updated', actor, 'Structured production direction saved')
        return self.mutate(project_id, expected_revision, update)

    def update_shots(self, project_id, shots, expected_revision, actor):
        if not isinstance(shots, list) or not 1 <= len(shots) <= 200:
            raise StudioError('invalid_shots', 'Provide between 1 and 200 ordered shots.')
        def update(p):
            old = {s['id']: s for s in p['shots']}
            changed = []
            seen = set()
            for item in shots:
                shot_id = item.get('id') or uid()
                if shot_id in seen or (item.get('id') and shot_id not in old):
                    raise StudioError('invalid_shot', 'Duplicate or unknown shot ID.')
                seen.add(shot_id)
                duration = item.get('duration_seconds', 4)
                if type(duration) is not int or not 1 <= duration <= 30:
                    raise StudioError('invalid_shot', 'Shot duration must be 1–30 seconds.')
                previous = old.get(shot_id, {})
                direction = normalize_direction(merge(previous.get('direction', {}), item.get('direction', {})))
                edit_duration = item.get('edit_duration_seconds', previous.get('edit_duration_seconds', duration))
                if type(edit_duration) not in [int, float] or not 0 < edit_duration <= 3600:
                    raise StudioError('invalid_shot', 'Retained edit duration must be a finite positive number.')
                changed.append({'id': shot_id, 'title': clean_text(item.get('title', 'Untitled shot'), 150),
                                'image_prompt': clean_text(item.get('image_prompt', '')),
                                'motion_prompt': clean_text(item.get('motion_prompt', '')),
                                'narration': clean_text(item.get('narration', '')),
                                'duration_seconds': duration, 'edit_duration_seconds': edit_duration, 'direction': direction,
                                'image_asset': None, 'video_asset': None})
            self._invalidate(p, 'visual_direction')
            p['shots'] = changed
            event(p, 'shots_changed', actor, f'{len(shots)} ordered shots saved')
        return self.mutate(project_id, expected_revision, update)

    def review(self, project_id, step, approve, note, expected_revision):
        if step not in STEPS:
            raise StudioError('invalid_step', 'Unknown workflow step.')
        def update(p):
            if self._next(p).get('step') != step or not p['steps'][step]['ready']:
                raise StudioError('review_blocked', 'This step is not ready for a current review.', 409)
            if approve:
                p['steps'][step]['status'] = 'approved'
                event(p, 'human_approved', 'user', step.replace('_', ' ') + ': ' + clean_text(note))
            else:
                self._invalidate(p, 'pilot' if step == 'production' else step)
                event(p, 'changes_requested', 'user', step.replace('_', ' ') + ': ' + clean_text(note))
            self._progress(p)
        return self.mutate(project_id, expected_revision, update)

    def _fingerprint(self, p, shot, kind):
        identity = {'epoch': p['epoch'], 'shot': shot['id'] if shot else None, 'kind': kind}
        if kind == 'video': identity['video_epoch'] = p.get('video_epoch', 0)
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    def claim_next(self, project_id, actor, request_id):
        if not clean_text(request_id, 200):
            raise StudioError('invalid_request', 'Provide a unique request_id, reused only for retries of this same handoff.')
        def update(p):
            retried = next((j for j in p['jobs'] if j.get('request_id') == request_id), None)
            if retried:
                return {'job': copy.deepcopy(retried), 'handoff': copy.deepcopy(retried['handoff']), 'already_claimed': True}
            action = self._next(p)
            if action['action'] != 'generate':
                return {'next_action': action, 'project_revision': p['revision'], 'job': None}
            shot = next(s for s in p['shots'] if s['id'] == action['shot_id'])
            fingerprint = self._fingerprint(p, shot, action['kind'])
            existing = next((j for j in p['jobs'] if j['fingerprint'] == fingerprint and j['status'] in ['awaiting_external_output', 'running', 'queued']), None)
            if existing:
                return {'job': existing, 'handoff': existing['handoff'], 'already_claimed': True}
            refs = [a for a in p['assets'] if a['id'] == shot['image_asset'] or a.get('role') == 'reference']
            prepared = prompt_for(p, shot, action['kind'])
            handoff = {'schema_version': 1, 'project_id': p['id'], 'project_name': p['name'], 'shot_id': shot['id'],
                       'shot_title': shot['title'], 'step': action['step'], 'kind': action['kind'],
                       'prompt': prepared['prompt'], 'generator_profile': prepared['generator_profile'],
                       'negative_prompt': prepared['negative_prompt'], 'separate_notes': prepared['separate_notes'],
                       'execution_mode': p['settings']['generation_mode'],
                       'creative_settings': copy.deepcopy(p['settings']), 'narration': shot['narration'],
                       'duration_seconds': shot['duration_seconds'], 'references': copy.deepcopy(refs),
                       'return_inbox': str(self.inbox), 'expected_output': 'PNG/JPEG/WebP' if action['kind'] == 'image' else 'MP4',
                       'return_instructions': 'Save the generated file in return_inbox, then call return_generation with this job_id and the absolute output_path. Do not mark it complete without real media.'}
            job = {'id': uid(), 'shot_id': shot['id'], 'kind': action['kind'], 'step': action['step'],
                   'status': 'awaiting_external_output', 'actor': actor, 'request_id': request_id,
                   'created_at': now(), 'fingerprint': fingerprint, 'handoff': handoff}
            handoff['job_id'] = job['id']
            p['jobs'].append(job)
            event(p, 'generation_handoff', actor, f"{shot['title']}: {action['kind']} handoff created")
            return {'job': copy.deepcopy(job), 'handoff': copy.deepcopy(handoff), 'already_claimed': False}
        return self.mutate(project_id, None, update)

    def find_job(self, job_id):
        for p in self.all():
            if p.get('deleted_at'): continue
            for j in p['jobs']:
                if j['id'] == job_id:
                    return p, j
        raise StudioError('not_found', 'Generation job not found.', 404)

    def return_result(self, job_id, output_path, actor):
        project, job = self.find_job(job_id)
        if job.get('asset_id'):
            return {'asset': next(a for a in project['assets'] if a['id'] == job['asset_id']), 'next_action': self._next(project)}
        if job['status'] in ['canceled', 'failed', 'interrupted']:
            raise StudioError('job_closed', 'This job is closed. Claim a new handoff.', 409)
        source, metadata = checked_file(output_path, [self.inbox, self.media_root], job['kind'])
        def update(p):
            current = next(j for j in p['jobs'] if j['id'] == job_id)
            if current.get('asset_id'):
                return {'asset': next(a for a in p['assets'] if a['id'] == current['asset_id']), 'next_action': self._next(p)}
            if current['status'] in ['canceled', 'failed', 'interrupted']:
                raise StudioError('job_closed', 'This job was closed before the return completed.', 409)
            shot = next((s for s in p['shots'] if s['id'] == current['shot_id']), None)
            stale = not shot or self._fingerprint(p, shot, current['kind']) != current['fingerprint']
            asset_id = uid()
            dest = self.media_root / p['id'] / (asset_id + metadata['suffix'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            asset = {'id': asset_id, 'shot_id': current['shot_id'], 'kind': current['kind'], 'stale': stale,
                     'path': str(dest), 'url': f'/api/studio/media/{p["id"]}/{dest.name}', 'created_at': now(), **metadata}
            p['assets'].append(asset)
            current.update(status='succeeded_stale' if stale else 'succeeded', asset_id=asset_id, completed_at=now())
            if not stale:
                shot[current['kind'] + '_asset'] = asset_id
            self._progress(p)
            event(p, 'generation_returned', actor, ('Earlier revision retained: ' if stale else 'Media received: ') + current['handoff']['shot_title'])
            return {'asset': copy.deepcopy(asset), 'next_action': self._next(p)}
        return self.mutate(project['id'], None, update)

    def cancel_job(self, job_id, actor):
        project, _ = self.find_job(job_id)
        def update(p):
            job = next(j for j in p['jobs'] if j['id'] == job_id)
            if job['status'] == 'running':
                raise StudioError('cannot_cancel', 'Provider execution is in progress. It cannot be safely canceled by this adapter.', 409)
            if job['status'] not in ['awaiting_external_output', 'queued']:
                raise StudioError('job_closed', 'Job is already closed.', 409)
            job['status'] = 'canceled'
            event(p, 'job_canceled', actor, job_id)
        return self.mutate(project['id'], None, update)

    def import_reference(self, project_id, path, name, expected_revision, actor):
        source, metadata = checked_file(path, [self.inbox, self.media_root], 'image')
        def update(p):
            self._invalidate(p, 'visual_direction')
            asset_id = uid()
            dest = self.media_root / p['id'] / (asset_id + metadata['suffix'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            p['assets'].append({'id': asset_id, 'kind': 'image', 'role': 'reference', 'name': clean_text(name, 150), 'path': str(dest), 'url': f'/api/studio/media/{p["id"]}/{dest.name}', 'stale': False, **metadata})
            event(p, 'reference_imported', actor, name)
        return self.mutate(project_id, expected_revision, update)

    def import_final(self, project_id, path, expected_revision, actor):
        source, metadata = checked_file(path, [self.inbox, self.media_root], 'final_video')
        def update(p):
            if self._next(p).get('step') != 'final_review':
                raise StudioError('step_blocked', 'Complete the editor handoff first.', 409)
            self._invalidate(p, 'final_review')
            asset_id = uid()
            dest = self.media_root / p['id'] / (asset_id + '.mp4')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            p['assets'].append({'id': asset_id, 'kind': 'final_video', 'path': str(dest), 'url': f'/api/studio/media/{p["id"]}/{dest.name}', 'stale': False, **metadata})
            p['documents']['final_review'] = {'text': 'External edit returned for final review.', 'export_asset_id': asset_id}
            p['steps']['final_review'] = {'ready': True, 'status': 'draft'}
            self._progress(p)
            event(p, 'final_edit_returned', actor, 'External edit attached')
        return self.mutate(project_id, expected_revision, update)

    def editor_handoff(self, project_id):
        p = self.get(project_id)
        return {'project_id': p['id'], 'project_name': p['name'], 'settings': p['settings'],
                'shots': [{**s, 'video': next((a for a in p['assets'] if a['id'] == s['video_asset']), None)} for s in p['shots']],
                'instructions': 'Assemble these takes in your preferred editor. Return the final MP4 for final review.',
                'ready': all(p['steps'][s]['status'] in ['approved', 'auto_proceeded'] for s in STEPS[:5])}
