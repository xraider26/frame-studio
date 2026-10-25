"""Historical human recipe endorsements backed by real inspected compatible media."""
import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from .assets import checked_file
from .creative import effective_direction
from .production import criteria_for
from .store import StudioError, load


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def project_snapshot(p, template):
    from .saved_templates import recipe_snapshot
    source = p['id'] == template.get('source_project_id')
    selected_shot = template.get('settings_shot_id', '') if source else ''
    snapshot = recipe_snapshot(p, template['sections'], selected_shot)
    if 'story' in snapshot and not source:
        # The portable story is identical after its generated shot IDs are restored.
        mapping = p.get('template_source', {}).get('shot_id_map', {})
        inverse = {new: old for old, new in mapping.items()}
        for shot in snapshot['story']['shots']:
            shot['id'] = inverse.get(shot['id'], shot['id'])
            action = shot['direction']['action']
            action['continuity_from'] = inverse.get(action['continuity_from'], action['continuity_from'])
    return snapshot


def usage(projects, template):
    matched = [p for p in projects if p['id'] == template.get('source_project_id') or p.get('template_source', {}).get('id') == template['id']]
    costs, rows = {}, []
    for p in matched:
        defects = sum(bool(r.get('defect')) or any(v is False for v in r.get('criteria', {}).values()) for a in p['assets'] for r in (a.get('review_history') or ([a['review']] if a.get('review') else [])))
        rows.append({'id': p['id'], 'name': p['name'], 'revision': p['revision'], 'source': p['id'] == template.get('source_project_id'),
                     'deleted': bool(p.get('deleted_at')), 'template_source': p.get('template_source'), 'attempts': len(p['jobs']),
                     'selected_video_shots': sum(bool(s.get('video_asset')) for s in p['shots']), 'observed_defects': defects})
        for job in p['jobs']:
            cost = job.get('cost', {})
            unit = cost.get('unit') or p['production']['resources']['unit']
            group = costs.setdefault(unit, {'unit': unit, 'reported_actual': Decimal(0), 'planned_unsettled': Decimal(0), 'unknown_actual_jobs': 0, 'unknown_exposure_jobs': 0, 'jobs': 0})
            group['jobs'] += 1
            if cost.get('actual') is not None:
                group['reported_actual'] += Decimal(str(cost['actual']))
            else:
                group['unknown_actual_jobs'] += 1
                if cost.get('planned') is None:
                    group['unknown_exposure_jobs'] += 1
                else:
                    group['planned_unsettled'] += Decimal(str(cost['planned']))
    return {'usage_count': sum(p.get('template_source', {}).get('id') == template['id'] for p in matched), 'projects': rows,
            'costs': [{**c, 'reported_actual': float(c['reported_actual']), 'planned_unsettled': float(c['planned_unsettled'])} for c in costs.values()],
            'observed_defects': sum(r['observed_defects'] for r in rows)}


class RecipeEvidence:
    def recipe_metrics(self, template_id):
        with self.connect() as conn:
            row = conn.execute('SELECT payload FROM studio_templates WHERE id=?', (template_id,)).fetchone()
            if not row:
                raise StudioError('template_not_found', 'Saved recipe no longer exists.', 404)
            t = json.loads(row[0])
            projects = [load(r[0]) for r in conn.execute('SELECT payload FROM studio_projects')]
        return {'template_id': t['id'], 'template_revision': t['revision'], 'snapshot_hash': t.get('snapshot_hash'),
                'source_project_id': t.get('source_project_id'), 'source_project_revision': t.get('source_project_revision'),
                'settings_shot_id': t.get('settings_shot_id', ''), 'evidence': t.get('evidence', []),
                'scope': 'Historical human observations of the recorded recipe inputs and selected assets only; future output quality is untested.',
                **usage(projects, t)}

    def _recipe_asset_evidence(self, p, shot, kind):
        key = shot.get(kind + '_asset')
        asset = next((a for a in p['assets'] if a['id'] == key and a.get('kind') == kind and a.get('shot_id') == shot['id'] and not a.get('role')), None)
        if not asset or asset.get('stale'):
            raise StudioError('recipe_evidence_missing', 'Select a current compatible video take for every shot in the evidence scope.', 409)
        job = next((j for j in p['jobs'] if j.get('asset_id') == key), {})
        if asset.get('input_signature') != self._input_signature(p, shot, kind) and job.get('fingerprint') != self._fingerprint(p, shot, kind):
            raise StudioError('recipe_evidence_incompatible', 'Selected media used different inputs. Generate or select a compatible take.', 409)
        path, metadata = checked_file(asset.get('path', ''), [self.media_root], kind)
        review = asset.get('review', {})
        required = {'image'} if kind == 'image' else {'beginning', 'middle', 'end'}
        criteria = criteria_for(p, shot, kind)
        from .calibration import check_state
        if not review or not required <= set(review.get('inspected', [])) or review.get('defect', '').strip() or any(check_state(v) in {'fail', 'blocked'} for v in review.get('criteria', {}).values()) or any(check_state(review.get('criteria', {}).get(c)) != 'pass' for c in criteria):
            raise StudioError('recipe_evidence_unreviewed', 'Inspect the full selected media, pass every effective criterion and resolve all reported defects before endorsement.', 409)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return {'id': key, 'kind': kind, 'shot_id': shot['id'], 'input_signature': self._input_signature(p, shot, kind),
                'file_sha256': digest.hexdigest(), 'file_bytes': path.stat().st_size, 'media': metadata,
                'review': copy.deepcopy(review), 'required_criteria': criteria}

    def endorse_recipe(self, template_id, project_id, note, expected_revision, template_revision, level='pilot'):
        if level not in ['pilot', 'production'] or not isinstance(note, str) or not note.strip() or len(note) > 8000:
            raise StudioError('invalid_recipe_evidence', 'Choose pilot/production and add a human review note of at most 8000 characters.')
        if type(expected_revision) is not int or type(template_revision) is not int:
            raise StudioError('invalid_revision', 'Project and template revisions are required.')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT payload FROM studio_templates WHERE id=?', (template_id,)).fetchone()
            if not row:
                raise StudioError('template_not_found', 'Saved recipe no longer exists.', 404)
            t = json.loads(row[0])
            if t['revision'] != template_revision:
                raise StudioError('template_revision_conflict', 'Recipe changed. Refresh before recording evidence.', 409)
            row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (project_id,)).fetchone()
            if not row:
                raise StudioError('not_found', 'Evidence project no longer exists.', 404)
            p = load(row[0])
            if p.get('deleted_at') or p['revision'] != expected_revision:
                raise StudioError('revision_conflict', 'Evidence project changed. Refresh before recording evidence.', 409)
            if not t.get('snapshot_hash') or snapshot_hash(project_snapshot(p, t)) != t['snapshot_hash']:
                raise StudioError('recipe_inputs_mismatch', 'Project inputs do not match this saved recipe. Save a new recipe for changed inputs.', 409)
            if not p['shots']:
                raise StudioError('recipe_evidence_missing', 'A reviewed selected video is required.', 409)
            shots = list(p['shots']) if level == 'production' else [p['shots'][0]]
            look_shot = t.get('settings_shot_id') if p['id'] == t.get('source_project_id') else None
            if look_shot:
                extra = next((s for s in p['shots'] if s['id'] == look_shot), None)
                if extra and extra not in shots:
                    shots.append(extra)
            assets = []
            for shot in shots:
                if 'settings' in t['sections'] and 'story' not in t['sections'] and (level == 'production' or not look_shot or shot['id'] == look_shot):
                    recipe_project = copy.deepcopy(p)
                    recipe_project['settings'] = t['snapshot']['settings']['settings']
                    recipe_project['production']['defaults'] = t['snapshot']['settings']['defaults']
                    expected_look = effective_direction(recipe_project, {'direction': {}})
                    observed_look = effective_direction(p, shot)
                    look_fields = ['camera', 'lighting', 'art', 'environment', 'mood', 'generation_mode', 'technique_ids']
                    if any(expected_look[k] != observed_look[k] for k in look_fields):
                        raise StudioError('recipe_inputs_mismatch', 'Inspected shot overrides the saved recipe look. Capture that shot as a new recipe or use matching output.', 409)
                if shot.get('image_asset'):
                    assets.append(self._recipe_asset_evidence(p, shot, 'image'))
                assets.append(self._recipe_asset_evidence(p, shot, 'video'))
            evidence = {'id': uuid.uuid4().hex, 'level': level, 'actor': 'user', 'at': datetime.now(timezone.utc).isoformat(),
                        'note': note.strip(), 'project_id': p['id'], 'project_revision': p['revision'], 'template_revision': t['revision'],
                        'snapshot_hash': t['snapshot_hash'], 'assets': assets,
                        'scope': 'First selected video and source-look shot' if level == 'pilot' else 'Every selected shot video; final edit/delivery not evaluated'}
            t.setdefault('evidence', []).append(evidence)
            t['revision'] += 1
            conn.execute('UPDATE studio_templates SET payload=? WHERE id=?', (json.dumps(t), template_id))
        return self.recipe_metrics(template_id)
