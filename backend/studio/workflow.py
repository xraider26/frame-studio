from .creator_chat import creator_authority
import copy
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .handoffs import ContextReads, build_execution_packet, serialize_claim, serialize_project
from .assets import checked_file
from .store import Store, StudioError
from .templates import DEFAULT_SETTINGS, STEPS, TEMPLATES, active_steps
from .generators import VIDEO_PROFILES, IMAGE_PROFILES, prompt_for, validate_template
from .exports import export_project
from .creative import default_production, Direction, Production, merge, validated, normalize_direction, effective_direction
from .preflight import preflight, references_for
from .production import ProductionTools, quality_passed, criteria_for
from .resources import resource_gate
from .saved_templates import SavedTemplates
from .batching import Batching
from .dispatch import Dispatch
from .identity import Identity
from .recipes import seed_recipe, recipe_context, retime_seeded_shots
from .recipe_trials import RecipeTrials
from .agent_rules import AgentRules
from .sequences import Sequences, sequence_context
from .calibration import Calibration, default_calibration, calibration_action, calibration_state, style_contract_signature, shot_style_accepted, missing_references, remember_calibration_pending, production_fidelity_action
from .execution_evidence import ExecutionEvidence, build_rule_application, rule_blockers, execution_contract, validate_execution
from .generation_setup import generation_setup_state, validate_generation_setup, selection_fingerprint, selection_ready


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


def event(p, kind, actor, message):
    from .creator_chat import current_decision
    decision = current_decision()
    if decision and actor == 'user':
        actor = decision['actor']
    p['history'].append({'at': now(), 'type': kind, 'actor': actor[:100], 'message': message[:1000]})


def clean_text(value, limit=12000):
    if not isinstance(value, str) or len(value) > limit:
        raise StudioError('invalid_input', f'Text must be a string of at most {limit} characters.')
    return value.strip()


class Studio(ContextReads, ExecutionEvidence, Calibration, Sequences, AgentRules, Batching, Dispatch, Identity, SavedTemplates, RecipeTrials, ProductionTools, Store):
    def __init__(self, db_path, media_root, inbox):
        super().__init__(db_path)
        self.media_root, self.inbox = Path(media_root).resolve(), Path(inbox).resolve()
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.inbox.mkdir(parents=True, exist_ok=True)

    def create_project(self, name, template_id, request_id=None, actor='user', allow_template_policy=True, output_type='video', settings=None, generation_setup=None):
        if request_id:
            for p in self.all():
                if p.get('request_id') == request_id:
                    return p
        return self.insert(self._build_project(name, template_id, request_id, actor, allow_template_policy, output_type, settings, generation_setup))

    def _build_project(self, name, template_id, request_id=None, actor='user', allow_template_policy=True, output_type='video', settings=None, generation_setup=None):
        if output_type not in ['image', 'video']:
            raise StudioError('invalid_output_type', 'Choose image or video output.')
        if settings is not None:
            settings = self._validate_settings(settings)
        if template_id == 'custom' and output_type == 'image':
            template_id = 'image-custom'
        saved = self.get_saved_template(template_id) if isinstance(template_id, str) and template_id.startswith('saved-') else None
        if saved:
            template_id = saved['base_template_id']
        template = next((t for t in TEMPLATES if t['id'] == template_id), None)
        if not template or not clean_text(name, 150):
            raise StudioError('invalid_input', 'Choose a valid template and project name.')
        kind = saved.get('output_type', 'video') if saved else template['output_type']
        if kind != output_type:
            raise StudioError('template_output_mismatch', 'Choose a template matching the project output type: ' + output_type + '.')
        p = {'id': uid(), 'name': name.strip(), 'template_id': template_id, 'revision': 1, 'schema_version': 2,
             'created_at': now(), 'request_id': request_id, 'epoch': 1, 'output_type': output_type, 'creative_intake_required': True,
             'settings': dict(copy.deepcopy(DEFAULT_SETTINGS), aspect_ratio=template['aspect']), 'documents': {},
             'approval_policy': {s: False for s in STEPS},
             'steps': {s: {'ready': False, 'status': 'draft'} for s in STEPS},
             'shots': [{'id': uid(), 'title': title, 'image_prompt': '', 'motion_prompt': '', 'narration': '', 'duration_seconds': 4, 'image_asset': None, 'video_asset': None} for title in (template['structure'][:1] if output_type == 'image' else template['structure'])],
             'assets': [], 'jobs': [], 'history': [], 'production': default_production(template_id)}
        for shot in p['shots']:
            shot.update(direction=Direction().model_dump(), edit_duration_seconds=shot['duration_seconds'], edit_in_seconds=0)
        seed_recipe(p, preserve=False)
        if saved:
            sections = [s for s in saved['sections'] if s != 'workflow']
            if 'settings' in sections and 'story' not in sections:
                for shot in p['shots']:
                    for group in ['camera', 'lighting', 'art']:
                        shot['direction'][group] = Direction().model_dump()[group]
            self._restore_template(p, saved, sections)
            if 'settings' in sections and 'story' not in sections:
                retime_seeded_shots(p)
        if settings:
            p['settings'].update(copy.deepcopy(settings))
        if generation_setup is not None:
            p['calibration'] = default_calibration()
            self._apply_generation_setup(p, generation_setup, actor)
        self._progress(p)
        event(p, 'created', actor, 'Project created from ' + template['name'])
        return p

    def start_project_setup(self, project_id=None, output_type=None):
        return generation_setup_state(self.get(project_id) if project_id else None, output_type)

    def _apply_generation_setup(self, p, setup, actor):
        before = copy.deepcopy(p)
        patch = validate_generation_setup(setup, p['output_type'])
        old = p.get('generation_setup') or {'version': 1}
        combined = {k: copy.deepcopy(old[k]) for k in ('version', 'image', 'video') if k in old}
        combined.update(patch)
        changed = [kind for kind in ('image', 'video') if old.get(kind) != combined.get(kind)]
        combined['selection_fingerprint'] = selection_fingerprint(combined)
        combined['assertion_authority'] = 'human_ui' if actor == 'user' else 'user_instruction_relayed' if creator_authority(actor) else 'agent_reported'
        combined['recorded_by'] = actor
        p['generation_setup'] = combined
        from .creative import Capabilities
        observations = p['production'].setdefault('capabilities_by_kind', {'image': Capabilities().model_dump(), 'video': Capabilities().model_dump()})
        for kind in changed:
            observations[kind] = Capabilities().model_dump()
            item = combined.get(kind)
            if item:
                p['settings'][kind + '_generator'] = item['profile']
                p['settings'][kind + '_model'] = item['model'] or ''
        image = combined.get('image')
        if image:
            p['settings']['generation_mode'] = 'api' if image['executor'] in {'api', 'comfyui'} else 'external_agent'
        self._guard_calibration_mutation(before, p, actor)
        # The legacy field is retained for historical/export consumers, never promoted to observations.
        if changed:
            self._invalidate_selected(p, {shot['id']: changed for shot in p['shots']})
        return changed

    def _unconfirm_changed_generator_fields(self, p, old_settings, source='legacy_unconfirmed'):
        if not p.get('generation_setup'):
            return
        from .creative import Capabilities
        for kind in ('image', 'video'):
            if any(p['settings'][kind + suffix] != old_settings[kind + suffix] for suffix in ('_model', '_generator')):
                item = p['generation_setup'].get(kind)
                if item:
                    item.update(profile=p['settings'][kind + '_generator'], model=p['settings'][kind + '_model'] or None,
                        model_version_status='specified' if p['settings'][kind + '_model'] else 'unknown', selection_source=source,
                        source_text='Compatibility settings changed; ask the creator to confirm the current generator.')
                p['production']['capabilities_by_kind'][kind] = Capabilities().model_dump()
        p['generation_setup']['selection_fingerprint'] = selection_fingerprint(p['generation_setup'])

    def set_generation_setup(self, project_id, setup, expected_revision, actor):
        from .agent_rules import validate_revision
        validate_revision(expected_revision)
        def update(p):
            changed = self._apply_generation_setup(p, setup, actor)
            self._progress(p)
            event(p, 'generation_setup_saved', actor, 'Generator selection assertion saved: ' + ', '.join(changed))
        return self.mutate(project_id, expected_revision, update)

    def require_generation_setup(self, project_id, kind='image'):
        p = self.get(project_id)
        if p.get('generation_setup') and not selection_ready(p['generation_setup'].get(kind)):
            raise StudioError('generation_setup_required', 'Call start_project_setup and save the creator selection with set_generation_setup before creative preparation or generation.', 409)

    def list_projects(self):
        return [{k: p[k] for k in ['id', 'name', 'template_id', 'revision', 'created_at', 'output_type']} for p in self.all() if not p.get('deleted_at')]

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

    def duplicate_project(self, project_id, name, actor, adopt_generation_setup=False):
        original = self.get(project_id)
        p = self.create_project(name or original['name'] + ' (copy)', ('image-custom' if original.get('output_type') == 'image' and not original['template_id'].startswith('image-') else original['template_id']), actor=actor, output_type=original.get('output_type', 'video'))
        def update(clone):
            clone['template_id'] = original['template_id']
            clone['settings'] = copy.deepcopy(original['settings'])
            clone['production'] = copy.deepcopy(original['production'])
            if adopt_generation_setup:
                clone['calibration'] = default_calibration()
                from .creative import Capabilities
                clone['generation_setup'] = {'version': 1, 'selection_fingerprint': selection_fingerprint({'version': 1})}
                clone['production']['capabilities_by_kind'] = {kind: Capabilities().model_dump() for kind in ('image', 'video')}
            clone['documents'] = {k: copy.deepcopy(v) for k, v in original['documents'].items() if k in ['brief', 'script']}
            clone['shots'] = [{**copy.deepcopy(s), 'id': uid(), 'image_asset': None, 'video_asset': None} for s in original['shots']]
            shot_ids = {old['id']: new['id'] for old, new in zip(original['shots'], clone['shots'])}
            asset_ids = {}
            for a in original['assets']:
                if a.get('role') != 'reference': continue
                source = Path(a['path']).resolve()
                if not source.is_relative_to(self.media_root) or not source.is_file(): continue
                asset_id = uid()
                asset_ids[a['id']] = asset_id
                dest = self.media_root / clone['id'] / (asset_id + source.suffix)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                clone['assets'].append({**copy.deepcopy(a), 'id': asset_id, 'path': str(dest), 'url': f'/api/studio/media/{clone["id"]}/{dest.name}', 'stale': False})
            for requirement in clone['production']['reference_requirements']:
                requirement['asset_ids'] = [asset_ids[key] for key in requirement['asset_ids'] if key in asset_ids]
            for entity in clone['production']['bible']:
                entity['asset_ids'] = [asset_ids.get(key, key) for key in entity['asset_ids']]
            for shot in clone['shots']:
                shot['direction']['action']['continuity_from'] = shot_ids.get(shot['direction']['action']['continuity_from'], '')
                shot['direction']['editorial']['audio_source_shot_id'] = shot_ids.get(shot['direction']['editorial']['audio_source_shot_id'], '')
                for ref in shot['direction']['references']:
                    ref['asset_id'] = asset_ids.get(ref['asset_id'], ref['asset_id'])
            for step in ['brief', 'script']:
                clone['steps'][step]['ready'] = bool(clone['documents'].get(step, {}).get('text'))
            self._progress(clone)
            event(clone, 'project_duplicated', actor, 'Plan and references copied; approvals, output takes and jobs start fresh')
        return self.mutate(p['id'], p['revision'], update)

    def export_handoff(self, project_id):
        return export_project(self, self.get(project_id))

    def get_project(self, project_id, detail="summary"):
        p = self.get(project_id)
        if production_fidelity_action(p):
            # Expose current readiness without rewriting historical creator decisions.
            p['steps']['visual_direction'] = {'ready': False, 'status': 'draft'}
        from .intake import creative_intake
        p['creative_intake'] = creative_intake(p)
        p['generation_setup_state'] = generation_setup_state(p)
        p['calibration_state'] = calibration_state(p)
        p['active_steps'] = list(active_steps(p))
        p['recipe_context'] = recipe_context(p)
        p['sequence_context'] = sequence_context(p)
        p['next_action'] = self._next(p)
        p['preflight'] = preflight(p)
        for asset in p['assets']:
            shot = next((s for s in p['shots'] if s['id'] == asset.get('shot_id')), None)
            if shot and not asset.get('role'):
                asset['required_checks'] = criteria_for(p, shot, asset['kind'])
        return serialize_project(p, detail)

    def activate_recipe(self, project_id, expected_revision, actor):
        if not creator_authority(actor):
            raise StudioError('human_only', 'Activating or migrating recipe standards belongs to the user.', 403)
        if type(expected_revision) is not int:
            raise StudioError('invalid_revision', 'Refresh the project revision before activating a recipe.')
        def update(p):
            if any(j['status'] == 'running' for j in p['jobs']):
                raise StudioError('job_running', 'Wait for running generation before changing recipe standards.', 409)
            seed_recipe(p, preserve=True)
            self._reopen(p, 'visual_direction')
            self._progress(p)
            event(p, 'recipe_activated', actor, 'Applied versioned course-informed standards; custom direction and approval/QC policy preserved')
        return self.mutate(project_id, expected_revision, update)

    def validate_project(self, project_id):
        return preflight(self.get(project_id))

    def preview_shot(self, project_id, shot_id):
        p = self.get(project_id)
        shot = next((s for s in p['shots'] if s['id'] == shot_id), None)
        if not shot:
            raise StudioError('not_found', 'Shot not found.', 404)
        result = {'source_revision': p['revision'], 'image': prompt_for(p, shot, 'image'), 'preflight': preflight(p, shot_id), 'references': references_for(p, shot, 'image' if p.get('output_type') == 'image' else 'video')}
        if p.get('output_type') != 'image':
            result['video'] = prompt_for(p, shot, 'video')
        return result

    def _progress(self, p):
        from .calibration import recover_baseline_approval
        recover_baseline_approval(p)
        remember_calibration_pending(p)
        if p.get('calibration') and p['calibration']['mode'] == 'calibration':
            p['calibration']['status'] = calibration_state(p)['status']
        for step in set(STEPS) - set(active_steps(p)):
            p['steps'][step] = {'ready': False, 'status': 'skipped'}
        for step, kind, shots in [('visual_direction', 'image', p['shots']), ('pilot', 'video', p['shots'][:1]), ('production', 'video', p['shots'])]:
            if step not in active_steps(p):
                continue
            ready = bool(shots) and all((kind != 'image' or shot_style_accepted(p, s)) and s[kind + '_asset'] and not missing_references(p, s, kind) and quality_passed(p, s, kind) and not preflight(p, s['id'], kind)['errors'] for s in shots)
            p['steps'][step]['ready'] = ready
            if not ready and p['steps'][step]['status'] in ['approved', 'auto_proceeded']:
                p['steps'][step]['status'] = 'draft'
        for step in active_steps(p):
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
        if p.get('generation_setup') and not selection_ready(p['generation_setup'].get('image')):
            state = generation_setup_state(p)
            return {'action': 'ask_creator', 'step': 'generation_setup', 'kind': 'image', 'questions': state['questions'], 'message': state['questions'][0]['prompt']}
        from .intake import creative_intake
        intake = creative_intake(p)
        if intake['status'] == 'needs_input':
            return {'action': 'ask_creator', 'step': 'brief', 'questions': intake['questions'], 'message': intake['instructions']}
        # Calibration is independent of step approval and cannot be skipped by a ready step.
        if all(p['steps'][step]['status'] in ['approved', 'auto_proceeded'] for step in ('brief', 'script') if step in active_steps(p)):
            gate = calibration_action(p)
            if gate:
                if gate['action'] == 'generate':
                    target = next(s for s in p['shots'] if s['id'] == gate['shot_id'])
                    budget = resource_gate(p, target, 'image', 'visual_direction', self._fingerprint(p, target, 'image'))
                    if budget:
                        return {**gate, 'action': 'resolve_resources', 'message': budget}
                return gate
            fidelity = production_fidelity_action(p)
            if fidelity:
                return fidelity
        for step in active_steps(p):
            state = p['steps'][step]
            if state['status'] in ['approved', 'auto_proceeded']:
                continue
            if state['ready']:
                return {'action': 'await_approval', 'step': step, 'message': 'Waiting for your review in the studio.'}
            if step in ['visual_direction', 'pilot', 'production']:
                kind = 'image' if step == 'visual_direction' else 'video'
                if p.get('generation_setup') and not selection_ready(p['generation_setup'].get(kind)):
                    state = generation_setup_state(p)
                    return {'action': 'ask_creator', 'step': 'generation_setup', 'kind': kind, 'questions': state['questions'], 'message': state['questions'][0]['prompt']}
                shots = p['shots'][:1] if step == 'pilot' else p['shots']
                shot = next((s for s in shots if not s[kind + '_asset'] or missing_references(p, s, kind) or not quality_passed(p, s, kind) or preflight(p, s['id'], kind)['errors']), None)
                if not shot:
                    return {'action': 'prepare_shots', 'step': step, 'message': 'Add shots to continue.'}
                missing = missing_references(p, shot, kind)
                if missing:
                    return {'action': 'ask_creator', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'reference_requirements': missing,
                            'message': 'Provide required '+', '.join(sorted({r['purpose'] for r in missing}))+' references for this production shot; environment calibration does not approve identity/product fidelity.'}
                if shot[kind + '_asset'] and not quality_passed(p, shot, kind):
                    if shot.get('quality_retry_attention', {}).get(kind):
                        return {'action': 'quality_attention', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': shot['quality_retry_attention'][kind]}
                    if shot.get('quality_retry_exhausted', {}).get(kind):
                        return {'action': 'quality_attention', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': 'Automatic quality retry limit reached. Inspect the defect and redesign or revise manually before spending again.'}
                    return {'action': 'record_quality', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'asset_id': shot[kind + '_asset'], 'criteria': criteria_for(p, shot, kind), 'message': 'Inspect the returned media and record the required quality checks.'}
                if not (shot['image_prompt'] if kind == 'image' else (effective_direction(p, shot)['action']['primary_action'] or shot['motion_prompt'])).strip():
                    return {'action': 'write_prompt', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': f"Prepare the {kind} prompt for {shot['title']}."}
                checks = preflight(p, shot['id'], kind)
                if checks['errors']:
                    return {'action': 'resolve_preflight', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': 'Resolve the blocking production checks before generating.', 'preflight': checks}
                budget = resource_gate(p, shot, kind, step, self._fingerprint(p, shot, kind))
                if budget:
                    return {'action': 'resolve_resources', 'step': step, 'shot_id': shot['id'], 'kind': kind, 'message': budget}
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
                if asset.get('role') != 'reference': asset['stale'] = True
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
        if not creator_authority(actor):
            self.require_generation_setup(project_id)
        if step not in ['brief', 'script', 'editor_handoff', 'final_review']:
            raise StudioError('invalid_step', 'This step requires returned image/video jobs, not a text completion.')
        text = clean_text(output.get('text', ''))
        if not text:
            raise StudioError('missing_output', 'Provide the actual step document or editing notes.')
        def update(p):
            self._guard_calibration_pending(p, actor)
            steps = active_steps(p)
            if not creator_authority(actor):
                action = self._next(p)
                if action['action'] != 'prepare_step' or action['step'] != step:
                    raise StudioError('step_blocked', 'Follow current next_action: ' + action['action'] + '. ' + action['message'] + ' Refresh get_project before continuing.', 409)
            if step not in steps:
                raise StudioError('invalid_step', 'This output type does not use that workflow step.')
            if any(p['steps'][s]['status'] not in ['approved', 'auto_proceeded'] for s in steps[:steps.index(step)]):
                raise StudioError('step_blocked', 'Complete earlier workflow steps first.', 409)
            if step in {'editor_handoff', 'final_review'}:
                for shot in p['shots']:
                    blocked = rule_blockers(build_rule_application(p, shot, 'image' if p.get('output_type') == 'image' else 'video', step), step)
                    if blocked: raise StudioError('execution_rules_blocked', 'Unresolved delivery rules: '+', '.join(r['rule_id'] for r in blocked), 409)
            image_final = step == 'final_review' and p.get('output_type') == 'image'
            image_ids = [shot.get('image_asset') for shot in p['shots']] if image_final else []
            if image_final and (not image_ids or any(not key or not any(a['id'] == key and a['kind'] == 'image' and not a.get('stale') and Path(a['path']).is_file() for a in p['assets']) for key in image_ids)):
                raise StudioError('missing_export', 'Select actual current images before final review.')
            if step == 'final_review' and not image_final and not output.get('export_asset_id'):
                raise StudioError('missing_export', 'Import the actual external edit as a final video before completing final review.')
            if step == 'final_review' and not image_final and not any(a['id'] == output['export_asset_id'] and a['kind'] == 'final_video' and not a['stale'] for a in p['assets']):
                raise StudioError('invalid_export', 'Final export is not attached to this project.')
            if p['steps'][step]['ready']:
                self._invalidate(p, step)
            p['documents'][step] = {'text': text, **({'export_asset_ids': image_ids} if image_final else {'export_asset_id': output['export_asset_id']} if step == 'final_review' else {})}
            p['steps'][step] = {'ready': True, 'status': 'draft'}
            self._progress(p)
            event(p, 'step_prepared', actor, step.replace('_', ' ') + ' prepared')
        return self.mutate(project_id, expected_revision, update)

    def _validate_settings(self, settings):
        if not isinstance(settings, dict) or any(k not in DEFAULT_SETTINGS for k in settings):
            raise StudioError('invalid_settings', 'Unknown creative setting.')
        for k, v in settings.items():
            if k == 'creative_intake':
                from .intake import validate_intake
                settings = copy.deepcopy(settings)
                settings[k] = validate_intake(v)
            elif k == 'duration_seconds':
                if type(v) is not int or not 1 <= v <= 3600:
                    raise StudioError('invalid_settings', 'Duration must be 1–3600 seconds.')
            else:
                clean_text(v, 3000)
        if 'aspect_ratio' in settings and settings['aspect_ratio'] not in ['16:9', '9:16', '1:1', '4:5', '2:3']:
            raise StudioError('invalid_settings', 'Choose 16:9, 9:16, 1:1, 4:5 or 2:3; verify support in the selected model.')
        for field, profiles in [('video_generator', VIDEO_PROFILES), ('image_generator', IMAGE_PROFILES)]:
            if field in settings and settings[field] not in [v['id'] for v in profiles]:
                raise StudioError('invalid_generator', 'Choose a supported generator profile or Custom.')
        if 'generation_mode' in settings and settings['generation_mode'] not in ['external_agent', 'api']:
            raise StudioError('invalid_mode', 'Choose external_agent or api execution.')
        for field in ['custom_video_template', 'custom_image_template']:
            if field in settings: validate_template(settings[field])
        return settings

    def update_settings(self, project_id, settings, expected_revision, actor):
        settings = self._validate_settings(settings)
        def update(p):
            if any(p['settings'][k] != v for k, v in settings.items()):
                before = copy.deepcopy(p)
                p['settings'].update(settings)
                self._guard_calibration_mutation(before, p, actor)
                self._unconfirm_changed_generator_fields(p, before['settings'])
                affected = self._changed_inputs(before, p)
                if affected: self._invalidate_selected(p, affected)
                else: self._reopen(p, 'editor_handoff')
                self._progress(p)
                event(p, 'settings_changed', actor, 'Creative settings updated; dependent outputs require review')
        return self.mutate(project_id, expected_revision, update)

    def update_production(self, project_id, production, expected_revision, actor):
        if not creator_authority(actor):
            self.require_generation_setup(project_id)
        if not isinstance(production, dict):
            raise StudioError('invalid_creative_record', 'Production must be an object.')
        def update(p):
            data = validated(Production, merge(p['production'], production))
            if not creator_authority(actor) and data['recipe'] != p['production']['recipe']:
                raise StudioError('human_only', 'Changing recipe standards belongs to the user.', 403)
            if not creator_authority(actor) and data['reference_requirements'] != p['production']['reference_requirements']:
                old = p['production']['reference_requirements']
                if any(r not in data['reference_requirements'] for r in old if r['required']):
                    raise StudioError('human_only', 'Only the creator can narrow required reference fidelity.', 403)
            self._guard_identity(p, data)
            ids = [e['id'] for e in data['bible']]
            if len(ids) != len(set(ids)) or any(not key for key in ids):
                raise StudioError('invalid_creative_record', 'Bible entities need distinct nonempty IDs.')
            if data != p['production']:
                before = copy.deepcopy(p)
                if data['resources']['unit'] != p['production']['resources']['unit'] and (p['jobs'] or any(a.get('cost') for a in p['assets'])):
                    raise StudioError('cost_unit_locked', 'Existing attempts use the current cost unit. Create a separate project for another unit.')
                p['production'] = data
                self._guard_calibration_mutation(before, p, actor)
                affected = self._changed_inputs(before, p)
                if affected: self._invalidate_selected(p, affected)
                if data['brief'] != before['production']['brief'] or data['story'] != before['production']['story']:
                    step = 'brief' if data['brief'] != before['production']['brief'] else 'script'
                    self._reopen(p, step)
                    for name in ['brief', 'script']:
                        p['steps'][name]['ready'] = bool(p['documents'].get(name, {}).get('text'))
                criteria_changed = any(criteria_for(before, old, 'image') != criteria_for(p, shot, 'image') for old, shot in zip(before['shots'], p['shots']))
                if criteria_changed or data['require_recorded_checks'] != before['production']['require_recorded_checks']:
                    self._reopen(p, 'visual_direction')
                self._progress(p)
                event(p, 'production_updated', actor, 'Structured production direction saved')
        return self.mutate(project_id, expected_revision, update)

    def update_shots(self, project_id, shots, expected_revision, actor):
        if not creator_authority(actor):
            self.require_generation_setup(project_id)
        if not isinstance(shots, list) or not 1 <= len(shots) <= 200 or any(not isinstance(s, dict) for s in shots):
            raise StudioError('invalid_shots', 'Provide between 1 and 200 ordered shots.')
        def update(p):
            before = copy.deepcopy(p)
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
                edit_in = item.get('edit_in_seconds', previous.get('edit_in_seconds', 0))
                if type(edit_in) not in [int, float] or not 0 <= edit_in <= 3600:
                    raise StudioError('invalid_shot', 'Source in-point must be a finite nonnegative number.')
                changed.append({'id': shot_id, 'title': clean_text(item.get('title', 'Untitled shot'), 150),
                                'image_prompt': clean_text(item.get('image_prompt', '')),
                                'motion_prompt': clean_text(item.get('motion_prompt', '')),
                                'narration': clean_text(item.get('narration', '')),
                                'duration_seconds': duration, 'edit_duration_seconds': edit_duration, 'edit_in_seconds': edit_in, 'direction': direction,
                                'image_asset': previous.get('image_asset'), 'video_asset': previous.get('video_asset'),
                                **({'input_versions': copy.deepcopy(previous['input_versions'])} if 'input_versions' in previous else {})})
                for key in ['quality_retries', 'quality_retry_exhausted', 'quality_retry_attention']:
                    if key in previous:
                        changed[-1][key] = copy.deepcopy(previous[key])
            p['shots'] = changed
            self._guard_calibration_mutation(before, p, actor)
            affected = self._changed_inputs(before, p)
            if affected:
                self._invalidate_selected(p, affected)
            elif changed != before['shots']:
                self._reopen(p, 'editor_handoff')
            if p['production']['require_recorded_checks'] and any(s['id'] in old and s['direction']['quality']['criteria'] != old[s['id']]['direction']['quality']['criteria'] for s in changed):
                self._reopen(p, 'visual_direction')
            self._progress(p)
            event(p, 'shots_changed', actor, f'{len(shots)} ordered shots saved')
        return self.mutate(project_id, expected_revision, update)

    def review(self, project_id, step, approve, note, expected_revision):
        if step not in STEPS:
            raise StudioError('invalid_step', 'Unknown workflow step.')
        def update(p):
            if approve and step in {'editor_handoff', 'final_review'}:
                for shot in p['shots']:
                    blocked = rule_blockers(build_rule_application(p, shot, 'image' if p.get('output_type') == 'image' else 'video', step), step)
                    if blocked: raise StudioError('execution_rules_blocked', 'Unresolved delivery rules: '+', '.join(r['rule_id'] for r in blocked), 409)
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
        if shot and 'input_versions' in shot:
            identity['input_version'] = shot['input_versions'].get(kind, 0)
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    def claim_next(self, project_id, actor, request_id, expected_revision=None):
        if not clean_text(request_id, 200):
            raise StudioError('invalid_request', 'Provide a unique request_id, reused only for retries of this same handoff.')
        if expected_revision is not None:
            p = self.get(project_id)
            retried = next((j for j in p['jobs'] if j.get('request_id') == request_id), None)
            if retried:
                if retried['actor'] != actor:
                    raise StudioError('job_owner', 'This request belongs to another executor. Read get_job; do not start duplicate paid work.', 403)
                return {'job': copy.deepcopy(retried), 'handoff': copy.deepcopy(retried['handoff']), 'already_claimed': True}
        context_blobs = []
        def update(p):
            block = self._dispatch_block(p)
            if block:
                raise StudioError('dispatch_blocked', block, 409)
            retried = next((j for j in p['jobs'] if j.get('request_id') == request_id), None)
            if retried:
                return {'job': copy.deepcopy(retried), 'handoff': copy.deepcopy(retried['handoff']), 'already_claimed': True}
            action = self._next(p)
            if action['action'] != 'generate':
                return {'next_action': action, 'project_revision': p['revision'], 'job': None}
            shot = next(s for s in p['shots'] if s['id'] == action['shot_id'])
            if p.get('calibration') and p['calibration']['mode'] == 'calibration' and not p['calibration'].get('representative_shot_id'):
                p['calibration']['representative_shot_id'] = shot['id']
            fingerprint = self._fingerprint(p, shot, action['kind'])
            existing = next((j for j in p['jobs'] if j['fingerprint'] == fingerprint and j['status'] in ['awaiting_external_output', 'running', 'queued']), None)
            if existing:
                return {'job': existing, 'handoff': existing['handoff'], 'already_claimed': True}
            block = self._dispatch_block(p, action['kind'])
            if block:
                raise StudioError('dispatch_blocked', block, 409)
            refs = references_for(p, shot, action['kind'])
            rules = build_rule_application(p, shot, action['kind'], action['step'])
            blockers = rule_blockers(rules, action['step'])
            if blockers:
                raise StudioError('execution_rules_blocked', '; '.join(r['rule_id']+': '+r['reason'] for r in blockers), 409)
            prepared = prompt_for(p, shot, action['kind'])
            handoff = {'schema_version': 2, 'project_id': p['id'], 'project_name': p['name'], 'shot_id': shot['id'],
                       'shot_title': shot['title'], 'step': action['step'], 'kind': action['kind'],
                       'prompt': prepared['prompt'], 'generator_profile': prepared['generator_profile'],
                       'prompt_contributions': prepared.get('prompt_contributions', []), 'compiled_fields': copy.deepcopy(prepared['compiled_fields']), 'rule_application': rules, 'execution_contract': execution_contract(prepared, refs, (p.get('generation_setup') or {}).get(action['kind'])),
                       'model': prepared.get('model'), 'model_guidance': copy.deepcopy(prepared.get('model_guidance')), 'creative_intent': copy.deepcopy(prepared.get('creative_intent')),
                       'negative_prompt': prepared['negative_prompt'], 'separate_notes': prepared['separate_notes'],
                       'warnings': prepared.get('warnings', []), 'image_requirements': prepared.get('image_requirements'),
                       'execution_mode': ('api' if p['generation_setup'][action['kind']]['executor'] in {'api', 'comfyui'} else 'external_agent') if p.get('generation_setup') else p['settings']['generation_mode'],
                       'generator_selection': copy.deepcopy((p.get('generation_setup') or {}).get(action['kind'])),
                       'creative_settings': copy.deepcopy(p['settings']), 'narration': shot['narration'],
                       'effective_direction': prepared['effective_direction'], 'production': copy.deepcopy(p['production']),
                       'identity_contract': copy.deepcopy(p.get('shared_identity')), 'idea_request': copy.deepcopy(p.get('idea_request')),
                       'acceptance_criteria': prepared['separate_notes']['acceptance_criteria'], 'recipe_contract': prepared['recipe_contract'], 'preflight': preflight(p, shot['id'], action['kind']),
                       'calibration_style_signature': style_contract_signature(p) if p.get('calibration') else None,
                       'required_media_checks': criteria_for(p, shot, action['kind']), 'input_signature': self._input_signature(p, shot, action['kind']),
                       'revision_context': {'reason': shot['direction']['quality']['revision_reason'],
                                            'previous_takes': [{k: a.get(k) for k in ['id', 'path', 'kind', 'stale', 'review']} for a in p['assets'] if a.get('shot_id') == shot['id'] and a['kind'] == action['kind']][-3:]},
                       'duration_seconds': shot['duration_seconds'], 'references': copy.deepcopy(refs),
                       'return_inbox': str(self.inbox), 'expected_output': 'PNG/JPEG/WebP' if action['kind'] == 'image' else 'MP4',
                       'return_instructions': 'Record exact submitted execution with record_generation_execution. Save the generated file in return_inbox, then call return_generation with this job_id and the absolute output_path. Do not mark it complete without real media.'}
            job = {'id': uid(), 'shot_id': shot['id'], 'kind': action['kind'], 'step': action['step'],
                   'cost': {'planned': p['production']['resources'][action['kind'] + '_cost'], 'actual': None, 'unit': p['production']['resources']['unit'], 'evidence': p['production']['resources']['cost_evidence']},
                   'status': 'awaiting_external_output', 'actor': actor, 'request_id': request_id,
                   'created_at': now(), 'fingerprint': fingerprint, 'handoff': handoff}
            handoff['job_id'] = job['id']
            from .agent_rules import contract_version, RULES_VERSION
            packet = build_execution_packet(self._contract_project(p), shot, action['kind'], action['step'], {'contract_version': contract_version(p), 'rules_version': RULES_VERSION})
            packet['source_revision'] = p['revision'] + 1
            context_blobs.extend(packet.pop('_context_blobs'))
            handoff['execution_packet'] = packet
            serialize_claim({'job': job, 'handoff': handoff, 'already_claimed': False})
            p['jobs'].append(job)
            event(p, 'generation_handoff', actor, f"{shot['title']}: {action['kind']} handoff created")
            return {'job': copy.deepcopy(job), 'handoff': copy.deepcopy(handoff), 'already_claimed': False}
        # A claim and its immutable context must commit together. A disk failure
        # must not leave a paid-work claim whose context can never be fetched.
        return self.mutate(project_id, expected_revision, update,
                           commit_hook=lambda conn: self._save_contexts(context_blobs, conn) if context_blobs else None)

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
            validation = validate_execution(current, current.get('execution', {}))
            asset = {'id': asset_id, 'execution_validation': validation, 'execution_state': 'match' if validation['state'] == 'match' else 'needs_review', 'job_id': current['id'], 'shot_id': current['shot_id'], 'kind': current['kind'], 'stale': stale,
                     'input_signature': current['handoff'].get('input_signature'), 'version': 1,
                     'calibration_style_signature': current['handoff'].get('calibration_style_signature'),
                     'path': str(dest), 'url': f'/api/studio/media/{p["id"]}/{dest.name}', 'created_at': now(), **metadata}
            p['assets'].append(asset)
            current.update(status=('succeeded_stale' if stale else 'succeeded') if validation['state'] == 'match' else 'needs_review', asset_id=asset_id, completed_at=now())
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

    def import_reference(self, project_id, path, name, expected_revision, actor, kind='image', entity_id=None):
        if type(expected_revision) is not int:
            raise StudioError('invalid_revision', 'Provide the current integer project revision.')
        if kind not in ['image', 'video']:
            raise StudioError('invalid_reference', 'Choose an image or motion-source video.')
        source, metadata = checked_file(path, [self.inbox, self.media_root], kind)
        def update(p):
            self._guard_calibration_pending(p, actor)
            entity = next((e for e in p['production']['bible'] if e['id'] == entity_id), None) if entity_id else None
            if entity_id and not entity:
                raise StudioError('not_found', 'Bible entity not found.', 404)
            if entity and any(e['id'] == entity_id for e in p.get('shared_identity', {}).get('entities', [])):
                raise StudioError('identity_locked', 'A canonical identity cannot be changed here. Edit the identity source project and sync the batch in Production queue.', 409)
            self._invalidate(p, 'visual_direction')
            asset_id = uid()
            dest = self.media_root / p['id'] / (asset_id + metadata['suffix'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            p['assets'].append({'id': asset_id, 'kind': kind, 'role': 'reference', 'name': clean_text(name, 150), 'path': str(dest), 'url': f'/api/studio/media/{p["id"]}/{dest.name}', 'stale': False, **metadata})
            if entity:
                entity['asset_ids'].append(asset_id)
                entity['version'] += 1
            self._progress(p)
            event(p, 'reference_imported', actor, name)
        return self.mutate(project_id, expected_revision, update)

    def import_final(self, project_id, path, expected_revision, actor):
        if self.get(project_id).get('output_type') == 'image':
            raise StudioError('invalid_output_type', 'Image projects review selected images directly.')
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
        if p.get('output_type') == 'image':
            raise StudioError('invalid_output_type', 'Image projects export selected images without an editor handoff.')
        cursor = 0
        shots = []
        for s in p['shots']:
            d = prompt_for(p, s, 'video')['effective_direction']
            duration = s.get('edit_duration_seconds', s['duration_seconds'])
            source_in = s.get('edit_in_seconds', 0)
            shots.append({**s, 'effective_direction': d, 'timeline_in': cursor, 'timeline_out': cursor + duration,
                          'source_in': source_in, 'source_out': source_in + duration,
                          'video': next((a for a in p['assets'] if a['id'] == s['video_asset']), None)})
            cursor += duration
        return {'schema_version': 2, 'project_id': p['id'], 'project_name': p['name'], 'settings': p['settings'], 'source_revision': p['revision'],
                'production': p['production'], 'sequence_context': sequence_context(p), 'preflight': preflight(p), 'shots': shots, 'edit_duration_seconds': cursor,
                'instructions': 'Assemble these takes in your preferred editor. J-cuts and L-cuts are deliberate editor notes: preserve specified source speech, room tone and audio continuity under cutaways. Check actual source audio and ranges; no internal audio edit has been rendered. Return the final MP4 for final review.',
                'ready': all(p['steps'][s]['status'] in ['approved', 'auto_proceeded'] for s in STEPS[:5])}
