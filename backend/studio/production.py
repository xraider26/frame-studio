"""Take evidence, selective dependencies and local media operations."""
import copy
import hashlib
import json
import math
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .assets import checked_file
from .creative import effective_direction
from .generators import prompt_for
from .preflight import references_for
from .resources import metrics
from .store import StudioError


def audit(p, actor, message):
    p['history'].append({'at': datetime.now(timezone.utc).isoformat(), 'type': 'production', 'actor': actor[:100], 'message': message[:1000]})


def criteria_for(shot, kind):
    return list(dict.fromkeys((['Identity and composition serve the shot'] if kind == 'image' else ['Identity, anatomy and physics remain coherent', 'Camera, lighting and background serve the shot', 'Audio and lip sync match the intended performance']) + [c for c in shot['direction']['quality']['criteria'] if c.strip()]))


def quality_passed(p, shot, kind):
    if not p['production']['require_recorded_checks']:
        return True
    asset = next((a for a in p['assets'] if a['id'] == shot[kind + '_asset']), {})
    review = asset.get('review', {})
    inspected = {'image'} if kind == 'image' else {'beginning', 'middle', 'end'}
    return bool(review) and not review.get('defect') and inspected <= set(review.get('inspected', [])) and all(review.get('criteria', {}).get(c) is True for c in criteria_for(shot, kind))


class ProductionTools:
    def _input_signature(self, p, shot, kind):
        prepared = prompt_for(p, shot, kind)
        value = {'prompt': prepared['prompt'], 'negative': prepared['negative_prompt'], 'aspect': prepared['aspect_ratio'],
                 'references': [{k: a.get(k) for k in ['id', 'slot', 'version', 'binding_role']} for a in references_for(p, shot, kind)]}
        if kind == 'video':
            value.update(duration=shot['duration_seconds'], sound=prepared['separate_notes']['sound'], mode=shot['direction']['generation_mode'])
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def _reopen(self, p, step):
        from .templates import STEPS
        for name in STEPS[STEPS.index(step):]:
            p['steps'][name] = {'ready': False, 'status': 'draft'}
        for asset in p['assets']:
            if asset['kind'] == 'final_video':
                asset['stale'] = True

    def _invalidate_selected(self, p, affected):
        affected = {key: set(kinds) for key, kinds in affected.items()}
        for kinds in affected.values():
            if 'image' in kinds: kinds.add('video')
        # A continuation or bound frame depends on the changed shot's image/motion.
        while True:
            count = sum(len(k) for k in affected.values())
            asset_ids = {a['id'] for a in p['assets'] if a.get('kind') in affected.get(a.get('shot_id'), set()) or a.get('source_shot') in affected}
            for asset in p['assets']:
                if asset.get('source_shot') in affected:
                    asset['stale'] = True
            for s in p['shots']:
                d = s['direction']
                if d['action']['continuity_from'] in affected or any(r['asset_id'] in asset_ids for r in d['references']):
                    affected.setdefault(s['id'], set()).update(['image', 'video'])
            if count == sum(len(k) for k in affected.values()):
                break
        earliest = 'editor_handoff'
        for shot in p['shots']:
            kinds = affected.get(shot['id'], set())
            if not kinds:
                continue
            if 'image' in kinds:
                kinds.add('video')
                earliest = 'visual_direction'
            elif earliest != 'visual_direction':
                earliest = 'pilot'
            versions = shot.setdefault('input_versions', {'image': 0, 'video': 0})
            for kind in kinds:
                versions[kind] += 1
                shot[kind + '_asset'] = None
                for asset in p['assets']:
                    if asset.get('shot_id') == shot['id'] and asset['kind'] == kind and not asset.get('role'):
                        asset['stale'] = True
                for job in p['jobs']:
                    if job['shot_id'] == shot['id'] and job['kind'] == kind and job['status'] in ['awaiting_external_output', 'queued']:
                        job['status'] = 'superseded'
        self._reopen(p, earliest)

    def _changed_inputs(self, before, after):
        old = {s['id']: s for s in before['shots']}
        affected = {}
        for shot in after['shots']:
            prior = old.get(shot['id'])
            for kind in ['image', 'video']:
                if not prior or self._input_signature(before, prior, kind) != self._input_signature(after, shot, kind):
                    affected.setdefault(shot['id'], set()).add(kind)
        return affected

    def record_take_review(self, project_id, asset_id, review, expected_revision, actor):
        if not isinstance(review, dict) or not isinstance(review.get('criteria', {}), dict) or any(type(v) is not bool for v in review.get('criteria', {}).values()):
            raise StudioError('invalid_review', 'Criteria must map checklist text to true/false.')
        if not isinstance(review.get('inspected', []), list) or any(v not in ['image', 'beginning', 'middle', 'end'] for v in review.get('inspected', [])):
            raise StudioError('invalid_review', 'Record the inspected image or beginning/middle/end.')
        def update(p):
            asset = next((a for a in p['assets'] if a['id'] == asset_id and not a.get('role')), None)
            if not asset:
                raise StudioError('not_found', 'Generated take not found.', 404)
            data = {'criteria': {str(k)[:200]: v for k, v in list(review.get('criteria', {}).items())[:60]},
                    'inspected': review.get('inspected', [])[:4], 'notes': str(review.get('notes', ''))[:8000],
                    'defect': str(review.get('defect', ''))[:8000], 'actor': actor, 'at': datetime.now(timezone.utc).isoformat()}
            asset.setdefault('review_history', []).append(copy.deepcopy(data))
            asset['review'] = data
            self._progress(p)
            audit(p, actor, 'Take inspection recorded: ' + asset_id)
        return self.mutate(project_id, expected_revision, update)

    def select_take(self, project_id, asset_id, expected_revision, actor):
        def update(p):
            asset = next((a for a in p['assets'] if a['id'] == asset_id and not a.get('role')), None)
            shot = next((s for s in p['shots'] if asset and s['id'] == asset.get('shot_id')), None)
            if not asset or not shot or asset['kind'] not in ['image', 'video']:
                raise StudioError('invalid_take', 'Choose an image/video take belonging to a current shot.')
            signature = self._input_signature(p, shot, asset['kind'])
            job = next((j for j in p['jobs'] if j.get('asset_id') == asset_id), {})
            if asset.get('input_signature') != signature and job.get('fingerprint') != self._fingerprint(p, shot, asset['kind']):
                raise StudioError('incompatible_take', 'This take used different creative inputs. Restore those inputs or generate a compatible take.', 409)
            if shot[asset['kind'] + '_asset'] == asset_id:
                return
            if asset['kind'] == 'image':
                self._invalidate_selected(p, {shot['id']: {'video'}})
            else:
                dependents = {s['id']: {'image', 'video'} for s in p['shots'] if s['direction']['action']['continuity_from'] == shot['id']}
                if dependents:
                    self._invalidate_selected(p, dependents)
                self._reopen(p, 'pilot')
            asset['stale'] = False
            shot[asset['kind'] + '_asset'] = asset_id
            self._progress(p)
            audit(p, actor, 'Explicitly selected compatible take: ' + asset_id)
        return self.mutate(project_id, expected_revision, update)

    def revise_shot(self, project_id, shot_id, kind, reason, expected_revision, actor):
        if kind not in ['image', 'video'] or not isinstance(reason, str) or not reason.strip():
            raise StudioError('invalid_revision', 'Choose image/video and name the defect or revision reason.')
        def update(p):
            shot = next((s for s in p['shots'] if s['id'] == shot_id), None)
            if not shot:
                raise StudioError('not_found', 'Shot not found.', 404)
            shot['direction']['quality']['revision_reason'] = reason[:8000]
            self._invalidate_selected(p, {shot_id: {kind}})
            self._progress(p)
            audit(p, actor, f'Targeted {kind} revision: {shot["title"]} — {reason}')
        return self.mutate(project_id, expected_revision, update)

    def extract_continuation(self, project_id, asset_id, expected_revision, actor):
        p = self.get(project_id)
        if p['revision'] != expected_revision:
            raise StudioError('revision_conflict', 'Refresh before extracting a continuation frame.', 409)
        video = next((a for a in p['assets'] if a['id'] == asset_id and a['kind'] == 'video' and not a['stale']), None)
        if not video:
            raise StudioError('invalid_take', 'Choose a current returned video take.')
        source, _ = checked_file(video['path'], [self.media_root], 'video')
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise StudioError('ffmpeg_missing', 'Install FFmpeg to extract a real continuation frame.')
        out = self.inbox / (uuid.uuid4().hex + '.png')
        try:
            subprocess.run([ffmpeg, '-y', '-sseof', '-0.1', '-i', str(source), '-frames:v', '1', str(out)], capture_output=True, timeout=30, check=True)
            _, metadata = checked_file(out, [self.inbox], 'image')
            def update(current):
                key = uuid.uuid4().hex
                dest = self.media_root / project_id / (key + '.png')
                shutil.copyfile(out, dest)
                current['assets'].append({'id': key, 'kind': 'image', 'role': 'reference', 'name': 'Continuation frame · inspect before use', 'version': 1,
                                          'source_video': asset_id, 'source_shot': video['shot_id'], 'path': str(dest), 'url': f'/api/studio/media/{project_id}/{dest.name}', 'stale': False, **metadata})
                # No automatic binding or claim of continuity; user chooses the following shot.
                audit(current, actor, 'Real continuation frame extracted; bind it explicitly after inspection')
            return self.mutate(project_id, expected_revision, update)
        finally:
            out.unlink(missing_ok=True)

    def repair_handoff(self, project_id, asset_id, defect, mask_asset_id, expected_revision, actor):
        p = self.get(project_id)
        if p['revision'] != expected_revision:
            raise StudioError('revision_conflict', 'Refresh before preparing an image repair.', 409)
        asset = next((a for a in p['assets'] if a['id'] == asset_id and a['kind'] == 'image'), None)
        mask = next((a for a in p['assets'] if a['id'] == mask_asset_id and a['kind'] == 'image'), None)
        if not asset or not isinstance(defect, str) or not defect.strip() or (mask_asset_id and not mask):
            raise StudioError('invalid_repair', 'Choose a real original image, describe the defect and select a valid mask if supplied.')
        return {'project_id': project_id, 'source_revision': p['revision'], 'original': asset, 'mask': mask, 'defect': defect[:8000],
                'preserve': 'Preserve identity, pose, composition, wardrobe, props and light outside the requested repair. Compare the actual result with the original.',
                'return_contract': 'Request an image revision for the affected shot; follow live next_action, claim its new job and return the actual edited file. References may also be imported explicitly. This handoff does not execute an image editor.'}

    def record_job_cost(self, project_id, job_id, actual, evidence, expected_revision, actor):
        if type(actual) not in [float, int] or not math.isfinite(actual) or not 0 <= actual <= 1_000_000_000 or not isinstance(evidence, str) or not evidence.strip():
            raise StudioError('invalid_cost', 'Report a finite nonnegative cost with actual provider/executor evidence.')
        def update(p):
            job = next((j for j in p['jobs'] if j['id'] == job_id), None)
            if not job:
                raise StudioError('not_found', 'Job not found.', 404)
            cost = job.setdefault('cost', {'planned': None, 'unit': p['production']['resources']['unit']})
            entry = {'actual': actual, 'evidence': evidence[:8000], 'actor': actor, 'at': datetime.now(timezone.utc).isoformat()}
            if cost.get('actual') != actual or cost.get('evidence') != evidence:
                job.setdefault('cost_history', []).append(copy.deepcopy(entry))
                cost.update(entry)
                audit(p, actor, f'Reported cost for {job_id}: {actual} {cost["unit"]}')
        return self.mutate(project_id, expected_revision, update)

    def production_metrics(self, project_id):
        return metrics(self.get(project_id))
