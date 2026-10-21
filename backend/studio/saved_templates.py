"""Reusable local project recipes. Snapshots contain planning inputs, never results."""
import copy
import json
import uuid
from datetime import datetime, timezone

from .store import StudioError, load
from .creative import Direction, effective_direction
from .templates import TEMPLATES
from .recipe_evidence import RecipeEvidence, snapshot_hash

SECTIONS = ['settings', 'workflow', 'story']


def selected_sections(value, available=SECTIONS):
    if not isinstance(value, list) or not value or any(not isinstance(v, str) or v not in available for v in value):
        raise StudioError('invalid_template_sections', 'Select at least one section contained in this template.')
    return list(dict.fromkeys(value))


def text(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise StudioError('invalid_template', f'Use {"nonempty " if required else ""}text of at most {limit} characters.')
    return value.strip()


def portable_direction(direction, include_entities):
    d = copy.deepcopy(direction)
    d['references'] = []
    d['quality']['known_defect'] = d['quality']['revision_reason'] = ''
    if not include_entities:
        d['action']['visible_entities'] = []
        d['sound']['speaker_id'] = ''
    return d


def summary(t):
    data = t['snapshot']
    base = next(v for v in TEMPLATES if v['id'] == t['base_template_id'])
    return {k: t[k] for k in ['id', 'name', 'description', 'revision', 'created_at', 'sections', 'base_template_id']} | {
        'saved': True, 'evidence_count': len(t.get('evidence', [])),
        'evidence_levels': sorted({e['level'] for e in t.get('evidence', []) if e.get('snapshot_hash') == t.get('snapshot_hash')}), 'aspect': data.get('settings', {}).get('settings', {}).get('aspect_ratio', base['aspect']),
        'structure': [s['title'] for s in data.get('story', {}).get('shots', [])] or base['structure'],
        'reference_note': 'Reattach reference files. Results, approvals, spending and observed model capabilities are not copied.'}


def recipe_snapshot(p, sections, settings_shot_id=''):
    snapshot = {}
    if 'settings' in sections:
        defaults = portable_direction(p['production']['defaults'], 'story' in sections)
        if settings_shot_id:
            shot = next((s for s in p['shots'] if s['id'] == settings_shot_id), None)
            if not shot:
                raise StudioError('shot_not_found', 'The chosen creative-default shot no longer exists. Refresh and choose another.', 409)
            look = effective_direction(p, shot)
            defaults = Direction().model_dump()
            for key in ['camera', 'lighting', 'art', 'environment', 'mood', 'generation_mode', 'technique_ids']:
                defaults[key] = copy.deepcopy(look[key])
            defaults['quality']['criteria'] = copy.deepcopy(look['quality']['criteria'])
        defaults['action']['continuity_from'] = ''
        snapshot['settings'] = {'settings': copy.deepcopy(p['settings']), 'defaults': defaults, 'format_rules': copy.deepcopy(p['production']['format_rules'])}
    if 'workflow' in sections:
        snapshot['workflow'] = {'approval_policy': copy.deepcopy(p['approval_policy']), 'require_recorded_checks': p['production']['require_recorded_checks']}
    if 'story' in sections:
        bible = copy.deepcopy(p['production']['bible'])
        for entity in bible:
            entity['asset_ids'] = []
        shots = []
        for s in p['shots']:
            shot = {k: copy.deepcopy(s[k]) for k in ['id', 'title', 'image_prompt', 'motion_prompt', 'narration', 'duration_seconds', 'edit_duration_seconds', 'edit_in_seconds']}
            shot['direction'] = portable_direction(s['direction'], True)
            shots.append(shot)
        snapshot['story'] = {k: copy.deepcopy(p['production'][k]) for k in ['brief', 'story']}
        snapshot['story'].update(bible=bible, shots=shots)
    return snapshot


class SavedTemplates(RecipeEvidence):
    def get_saved_template(self, template_id, expected_revision=None):
        with self.connect() as conn:
            row = conn.execute('SELECT payload FROM studio_templates WHERE id=?', (template_id,)).fetchone()
        if not row:
            raise StudioError('template_not_found', 'Saved template no longer exists. Refresh the template library.', 404)
        t = json.loads(row[0])
        if expected_revision is not None and t['revision'] != expected_revision:
            raise StudioError('template_revision_conflict', 'Template changed. Refresh before retrying.', 409)
        return t

    def list_saved_templates(self):
        with self.connect() as conn:
            return [summary(json.loads(r[0])) for r in conn.execute('SELECT payload FROM studio_templates ORDER BY rowid DESC')]

    def save_project_template(self, project_id, name, description, sections, expected_revision, settings_shot_id=''):
        sections = selected_sections(sections)
        name, description = text(name, 150, True), text(description, 2000)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (project_id,)).fetchone()
            if not row:
                raise StudioError('not_found', 'Project not found.', 404)
            p = load(row[0])
            if p.get('deleted_at') or p['revision'] != expected_revision:
                raise StudioError('revision_conflict', 'Project changed. Refresh before saving the template.', 409)
            snapshot = recipe_snapshot(p, sections, settings_shot_id)
            t = {'id': 'saved-' + uuid.uuid4().hex, 'schema_version': 1, 'name': name, 'description': description, 'revision': 1,
                 'created_at': datetime.now(timezone.utc).isoformat(), 'base_template_id': p['template_id'], 'sections': sections, 'snapshot': snapshot,
                 'source_project_id': p['id'], 'source_project_revision': p['revision'],
                 'settings_shot_id': settings_shot_id if 'settings' in sections else '', 'snapshot_hash': snapshot_hash(snapshot)}
            conn.execute('INSERT INTO studio_templates VALUES (?,?)', (t['id'], json.dumps(t)))
        return summary(t)

    def rename_project_template(self, template_id, name, description, expected_revision):
        name, description = text(name, 150, True), text(description, 2000)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            t = self.get_saved_template(template_id, expected_revision)
            t.update(name=name, description=description, revision=t['revision'] + 1)
            conn.execute('UPDATE studio_templates SET payload=? WHERE id=?', (json.dumps(t), template_id))
        return summary(t)

    def delete_project_template(self, template_id, expected_revision):
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.get_saved_template(template_id, expected_revision)
            conn.execute('DELETE FROM studio_templates WHERE id=?', (template_id,))
        return {'deleted': True, 'template_id': template_id}

    def _restore_template(self, p, t, sections):
        snapshot = t['snapshot']
        ids = {}
        if 'settings' in sections:
            data = copy.deepcopy(snapshot['settings'])
            if 'story' not in sections:
                data['defaults'] = portable_direction(data['defaults'], False)
            p['settings'].update(data['settings'])
            p['production'].update(defaults=data['defaults'], format_rules=data['format_rules'])
        if 'workflow' in sections:
            data = snapshot['workflow']
            p['approval_policy'] = copy.deepcopy(data['approval_policy'])
            p['production']['require_recorded_checks'] = data['require_recorded_checks']
        if 'story' in sections:
            data = copy.deepcopy(snapshot['story'])
            shots = data.pop('shots')
            ids = {s['id']: uuid.uuid4().hex for s in shots}
            for shot in shots:
                shot['id'] = ids[shot['id']]
                action = shot['direction']['action']
                action['continuity_from'] = ids.get(action['continuity_from'], '')
                shot.update(image_asset=None, video_asset=None)
            p['shots'] = shots
            p['production'].update(data)
            if 'settings' not in sections:
                # Retained creative defaults may point into the replaced cast/shot plan.
                defaults = p['production']['defaults']
                entities = {e['id'] for e in data['bible']}
                action = defaults['action']
                visible = [key for key in action['visible_entities'] if key in entities]
                if visible != action['visible_entities']:
                    action['headcount'] = None
                action['visible_entities'] = visible
                if action['continuity_from'] not in ids.values():
                    action['continuity_from'] = ''
                if defaults['sound']['speaker_id'] not in entities:
                    defaults['sound']['speaker_id'] = ''
                assets = {a['id']: a for a in p['assets']}
                defaults['references'] = [r for r in defaults['references'] if
                    (not r['entity_id'] or r['entity_id'] in entities) and r['asset_id'] in assets and
                    not assets[r['asset_id']].get('stale') and
                    (not assets[r['asset_id']].get('source_shot') or assets[r['asset_id']]['source_shot'] in ids.values())]
        self._preserve_identity(p)
        self._guard_identity(p, p['production'])
        p['template_source'] = {'id': t['id'], 'name': t['name'], 'revision': t['revision'], 'sections': sections,
                                'snapshot_hash': t.get('snapshot_hash', snapshot_hash(t['snapshot'])), 'shot_id_map': ids}

    def apply_project_template(self, project_id, template_id, sections, expected_revision, template_revision, actor):
        def update(p):
            t = self.get_saved_template(template_id, template_revision)
            chosen = selected_sections(sections, t['sections'])
            if any(j['status'] == 'running' for j in p['jobs']):
                raise StudioError('job_running', 'Wait for the running API generation before applying a template.', 409)
            before = copy.deepcopy(p)
            if 'story' in chosen:
                self._invalidate(p, 'brief')
                p['documents'] = {}
            self._restore_template(p, t, chosen)
            if 'story' not in chosen:
                affected = self._changed_inputs(before, p)
                if affected:
                    self._invalidate_selected(p, affected)
                else:
                    self._reopen(p, 'editor_handoff')
            if 'workflow' in chosen:
                self._reopen(p, 'brief')
                for step in ['brief', 'script']:
                    p['steps'][step]['ready'] = bool(p['documents'].get(step, {}).get('text'))
            self._progress(p)
            p['history'].append({'at': datetime.now(timezone.utc).isoformat(), 'type': 'template_applied', 'actor': actor,
                                 'message': f'Applied {t["name"]}: {", ".join(chosen)}; affected outputs and reviews reopened'})
        return self.mutate(project_id, expected_revision, update)
