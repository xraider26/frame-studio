"""Human observations of actual final edits, scoped to immutable production inputs."""
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone

from .assets import checked_file
from .recipes import recipe_context
from .store import StudioError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def file_evidence(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    return {'sha256': sha.hexdigest(), 'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}


def trial_inputs(p):
    selected = {s.get('image_asset') for s in p['shots']} | {s.get('video_asset') for s in p['shots']}
    return digest({'template': p['template_id'], 'settings': p['settings'],
                   'production': {k: p['production'][k] for k in ['recipe', 'brief', 'story', 'bible', 'defaults', 'capabilities', 'format_rules']},
                   'documents': p['documents'],
                   'shots': [{k: s.get(k) for k in ['id', 'direction', 'image_prompt', 'motion_prompt', 'narration', 'duration_seconds', 'edit_duration_seconds', 'edit_in_seconds', 'image_asset', 'video_asset']} for s in p['shots']],
                   'selected_reviews': [{k: a.get(k) for k in ['id', 'review', 'stale', 'input_signature']} for a in p['assets'] if a['id'] in selected]})


class RecipeTrials:
    def recipe_validation_summary(self):
        latest = {}
        trials = [t for p in self.all() for t in p.get('recipe_trials', [])]
        for t in sorted(trials, key=lambda v: v['at']):
            latest[(t['recipe_id'], t['recipe_version'], t['final_file']['sha256'])] = t
        groups = {}
        for trial in latest.values():
            key = trial['recipe_id']
            group = groups.setdefault(key, {'reviewed_outputs': 0, 'passed_outputs': 0, 'ideas': set(), 'models': set()})
            group['reviewed_outputs'] += 1
            group['passed_outputs'] += int(trial['passed'])
            group['ideas'].add(trial['idea'].strip().casefold())
            group['models'].add(trial['model_scope']['capabilities']['model'])
        return {k: {**v, 'ideas': len(v['ideas']), 'models': sorted(v['models']),
                    'scope': 'Historical reviewed unique final files, grouped by content format. Check each trial for recipe version and exact model/settings; not a quality guarantee.'} for k, v in groups.items()}

    def recipe_trials(self, project_id):
        p = self.get(project_id)
        signature = trial_inputs(p)
        assets = {a['id']: a for a in p['assets']}
        trials = []
        checked_sources = {}
        for recorded in p.get('recipe_trials', []):
            entry = copy.deepcopy(recorded)
            asset = assets.get(entry['asset_id'], {})
            from pathlib import Path
            file = Path(asset.get('path', ''))
            unchanged_file = file.is_file() and file.stat().st_size == entry['final_file']['bytes'] and file.stat().st_mtime_ns == entry['final_file']['mtime_ns']
            source_files_match = True
            for evidence in entry['shot_evidence']:
                source_asset = assets.get(evidence['id'], {})
                source = Path(source_asset.get('path', ''))
                if source_asset.get('stale', True) or not source.is_file() or not evidence.get('file_sha256'):
                    source_files_match = False
                    break
                if str(source) not in checked_sources:
                    checked_sources[str(source)] = file_evidence(source)['sha256']
                if checked_sources[str(source)] != evidence['file_sha256']:
                    source_files_match = False
                    break
            entry['matches_current_inputs'] = entry['input_hash'] == signature and not asset.get('stale', True) and unchanged_file and source_files_match
            trials.append(entry)
        context = recipe_context(p)
        return {'project_id': p['id'], 'revision': p['revision'], 'recipe_id': context.get('id'), 'recipe_version': context.get('version'),
                'final_checks': context.get('final_checks', []), 'trials': trials,
                'scope': 'Historical human assessments of these exact inputs and final files. Repeated ideas and real generator trials are still required to establish consistency. Still examples are not video trials.'}

    def record_recipe_trial(self, project_id, assessment, expected_revision, actor):
        if actor != 'user':
            raise StudioError('human_only', 'Final production assessment belongs to the human reviewer.', 403)
        if type(expected_revision) is not int or not isinstance(assessment, dict):
            raise StudioError('invalid_assessment', 'Use a current project revision and a structured final assessment.')
        note = assessment.get('note')
        idea = assessment.get('idea')
        defects = assessment.get('defects', '')
        if any(not isinstance(v, str) or len(v) > limit or not v.strip() for v, limit in [(note, 8000), (idea, 1000)]) or not isinstance(defects, str) or len(defects) > 8000:
            raise StudioError('invalid_assessment', 'Record the actual idea, human observations and any remaining defects.')
        def update(p):
            context = recipe_context(p)
            if not context['active']:
                raise StudioError('recipe_inactive', 'Activate a current recipe before recording a scoped production trial.', 409)
            caps = p['production']['capabilities']
            if not caps['confirmed'] or any(not caps.get(k, '').strip() for k in ['model', 'source', 'observed_at']):
                raise StudioError('model_scope_missing', 'Record the actual generator model, observed settings, source and date first.', 409)
            asset_id = assessment.get('asset_id')
            asset = next((a for a in p['assets'] if a['id'] == asset_id and a['kind'] == 'final_video' and not a.get('stale')), None)
            if not asset or p['documents'].get('final_review', {}).get('export_asset_id') != asset_id:
                raise StudioError('final_missing', 'Import and select the actual current external final edit first.', 409)
            path, media = checked_file(asset.get('path', ''), [self.media_root], 'final_video')
            checks = assessment.get('criteria', {})
            inspected = assessment.get('inspected')
            if (assessment.get('watched_full') is not True or not isinstance(assessment.get('inspected'), list)
                    or any(not isinstance(v, str) or v not in ['beginning', 'middle', 'end'] for v in inspected)
                    or not {'beginning', 'middle', 'end'} <= set(assessment['inspected'])
                    or not isinstance(checks, dict) or set(checks) != set(context['final_checks']) or any(type(v) is not bool for v in checks.values())):
                raise StudioError('inspection_missing', 'Watch the full final edit, inspect beginning/middle/end and explicitly assess every final criterion.', 409)
            passed = all(checks.values()) and not defects.strip()
            if passed:
                if abs(media['duration'] - p['settings']['duration_seconds']) > .5:
                    raise StudioError('final_runtime', 'Final duration differs from the intended runtime. Reconcile the edit or project target before a passing assessment.', 409)
                try:
                    w, h = [float(v) for v in p['settings']['aspect_ratio'].split(':')]
                except (ValueError, ZeroDivisionError):
                    raise StudioError('final_aspect', 'Choose a valid intended aspect ratio before assessment.', 409)
                if h <= 0 or abs(media['width'] / media['height'] - w / h) > .03:
                    raise StudioError('final_aspect', 'Final framing does not match the intended aspect ratio.', 409)
            if not p['shots']:
                raise StudioError('shot_evidence_missing', 'A production trial needs the actual selected shot media.', 409)
            shot_evidence = []
            for shot in p['shots']:
                if passed:
                    evidence = self._recipe_asset_evidence(p, shot, 'video')
                    if shot.get('edit_in_seconds', 0) + shot.get('edit_duration_seconds', shot['duration_seconds']) > evidence['media']['duration'] + .05:
                        raise StudioError('source_range_missing', 'A selected clip is shorter than its retained source range. Trim/reconcile the edit or replace the clip before passing production.', 409)
                    shot_evidence.append(evidence)
                    if shot.get('image_asset'):
                        shot_evidence.append(self._recipe_asset_evidence(p, shot, 'image'))
                else:
                    chosen = next((a for a in p['assets'] if a['id'] == shot.get('video_asset') and a['kind'] == 'video' and not a.get('stale')), None)
                    if not chosen:
                        raise StudioError('shot_evidence_missing', 'Select real current shot media before recording a production trial.', 409)
                    selected_path, selected_media = checked_file(chosen.get('path', ''), [self.media_root], 'video')
                    shot_evidence.append({'id': chosen['id'], 'shot_id': shot['id'], 'review': copy.deepcopy(chosen.get('review', {})), 'file_sha256': file_evidence(selected_path)['sha256'], 'media': selected_media})
            final_file = file_evidence(path)
            signature = trial_inputs(p)
            duplicate = next((e for e in p.get('recipe_trials', []) if e['input_hash'] == signature and e['final_file']['sha256'] == final_file['sha256'] and e['criteria'] == checks and e['defects'] == defects.strip()), None)
            if duplicate:
                return
            jobs = p['jobs']
            trial = {'id': uuid.uuid4().hex, 'recipe_id': context['id'], 'recipe_version': context['version'],
                     'project_id': p['id'], 'project_revision': p['revision'], 'asset_id': asset_id,
                     'actor': 'user', 'at': datetime.now(timezone.utc).isoformat(), 'idea': idea.strip(),
                     'note': note.strip(), 'defects': defects.strip(), 'passed': passed, 'criteria': copy.deepcopy(checks),
                     'watched_full': True, 'inspected': ['beginning', 'middle', 'end'], 'input_hash': signature,
                     'final_file': final_file, 'media': media, 'shot_evidence': shot_evidence,
                     'model_scope': {'settings': copy.deepcopy(p['settings']), 'capabilities': copy.deepcopy(caps)},
                     'attempts': len(jobs), 'costs': [copy.deepcopy(j.get('cost', {})) for j in jobs],
                     'coverage': context['coverage']['sha256']}
            p.setdefault('recipe_trials', []).append(trial)
        self.mutate(project_id, expected_revision, update)
        return self.recipe_trials(project_id)
