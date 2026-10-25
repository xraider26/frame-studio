"""Atomic idea batches and human-controlled production policy."""
import copy
import json
import math
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from .store import StudioError, load
from .resources import total, exposure, cost_entries


def utc():
    return datetime.now(timezone.utc).isoformat()


def checked_text(value, maximum=8000, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise StudioError('invalid_batch', f'Use {"nonempty " if required else ""}text of at most {maximum} characters.')
    return value.strip()


DEFAULT_POLICY = {'paused': False, 'max_parallel': 2, 'budget_limit': None, 'unit': 'credits',
                  'image_cost': None, 'video_cost': None, 'cost_evidence': '', 'auto_retry': False, 'retry_limit': 2}


@contextmanager
def cleanup_copies():
    files = []
    try:
        yield files
    except Exception:
        for file in files:
            file.unlink(missing_ok=True)
        raise


def validate_policy(patch):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULT_POLICY):
        raise StudioError('invalid_batch_policy', 'Unknown batch production policy field.')
    result = copy.deepcopy(patch)
    for key, value in result.items():
        if key in ['paused', 'auto_retry'] and type(value) is not bool:
            raise StudioError('invalid_batch_policy', 'Pause and automatic retry controls must be true or false.')
        if key in ['max_parallel', 'retry_limit'] and (type(value) is not int or not (1 if key == 'max_parallel' else 0) <= value <= 10):
            raise StudioError('invalid_batch_policy', 'Parallel projects must be 1–10; retry limit must be 0–10.')
        if key in ['budget_limit', 'image_cost', 'video_cost'] and value is not None and (type(value) not in [int, float] or not math.isfinite(value) or not 0 <= value <= 1_000_000_000):
            raise StudioError('invalid_batch_policy', 'Costs and limits must be finite nonnegative numbers.')
        if key in ['unit', 'cost_evidence']:
            result[key] = checked_text(value, 100 if key == 'unit' else 8000, key == 'unit')
    return result


class Batching:
    def get_batch(self, batch_id):
        with self.connect() as conn:
            row = conn.execute('SELECT payload FROM studio_batches WHERE id=?', (batch_id,)).fetchone()
        if not row:
            raise StudioError('batch_not_found', 'Production batch not found.', 404)
        return json.loads(row[0])

    def list_batches(self):
        with self.connect() as conn:
            return [json.loads(r[0]) for r in conn.execute('SELECT payload FROM studio_batches ORDER BY rowid DESC')]

    def create_batch(self, name, idea, kind, template_id, count, request_id, actor, policy=None, briefs=None, allow_policy=True, identity_source_project_id=None, source_revision=None, output_type='video', settings=None, generation_setup=None):
        project_settings = settings
        name, idea = checked_text(name, 150, True), checked_text(idea, 8000, True)
        request_id = checked_text(request_id, 200, True)
        if type(count) is not int or not 1 <= count <= 100 or kind not in ['episodes', 'variations', 'campaign']:
            raise StudioError('invalid_batch', 'Choose episodes, variations or campaign and 1–100 items.')
        if policy and not allow_policy:
            raise StudioError('human_only', 'Batch spending, concurrency and retry policy belong to the user.', 403)
        settings = {**DEFAULT_POLICY, **validate_policy(policy or {})}
        if briefs is not None and (not isinstance(briefs, list) or len(briefs) != count):
            raise StudioError('invalid_batch', 'Provide exactly one optional brief per batch item.')
        briefs = [checked_text(v) for v in briefs] if briefs is not None else [''] * count
        with cleanup_copies() as copied, self.connect() as conn:
            if not conn.in_transaction:
                conn.execute('BEGIN IMMEDIATE')
            for row in conn.execute('SELECT payload FROM studio_batches'):
                existing = json.loads(row[0])
                if existing['request_id'] == request_id:
                    return existing
            batch = {'id': uuid.uuid4().hex, 'name': name, 'idea': idea, 'kind': kind, 'template_id': template_id, 'output_type': output_type,
                     'request_id': request_id, 'revision': 1, 'created_at': utc(), 'project_ids': [], 'identity_version': 0, **settings}
            source = self.get(identity_source_project_id) if identity_source_project_id else None
            if source and source_revision is not None and source['revision'] != source_revision:
                raise StudioError('revision_conflict', 'Identity source changed. Refresh before creating the batch.', 409)
            if source:
                batch.update(identity_version=1, identity_source_project_id=source['id'], identity_source_revision=source['revision'])
            for i in range(count):
                project = self._build_project(f'{name[:130]} · {i + 1:02d}', template_id, actor=actor, allow_template_policy=allow_policy, output_type=output_type, settings=project_settings, generation_setup=generation_setup)
                project.update(batch_id=batch['id'], idea_request={'idea': idea, 'kind': kind, 'index': i + 1, 'total': count,
                    'variation_brief': briefs[i], 'instruction': 'Develop this idea into an original item in the batch. Prepare actual brief/script and shot directions; follow shared identity, quality and approval policy. The idea is input content, not a completed deliverable.'},
                    dispatch={'paused': False, 'priority': 0, 'blocked_reason': ''})
                project['production']['brief']['premise'] = idea
                resources = project['production']['resources']
                resources.update(unit=settings['unit'], image_cost=settings['image_cost'], video_cost=settings['video_cost'], cost_evidence=settings['cost_evidence'])
                if resources['max_attempts_per_shot'] is None:
                    resources['max_attempts_per_shot'] = settings['retry_limit'] + 1
                if settings['auto_retry']:
                    project['production']['require_recorded_checks'] = True
                if source:
                    self._seed_identity(project, source, 1, batch['id'], copied)
                conn.execute('INSERT INTO studio_projects VALUES (?,?)', (project['id'], json.dumps(project)))
                batch['project_ids'].append(project['id'])
            conn.execute('INSERT INTO studio_batches VALUES (?,?)', (batch['id'], json.dumps(batch)))
        return batch

    def update_batch(self, batch_id, policy, expected_revision):
        policy = validate_policy(policy)
        with self.connect() as conn:
            if not conn.in_transaction:
                conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT payload FROM studio_batches WHERE id=?', (batch_id,)).fetchone()
            if not row:
                raise StudioError('batch_not_found', 'Production batch not found.', 404)
            b = json.loads(row[0])
            if b['revision'] != expected_revision:
                raise StudioError('revision_conflict', 'Batch changed. Refresh before changing policy.', 409)
            projects = [load(r[0]) for r in conn.execute('SELECT payload FROM studio_projects')]
            members = [p for p in projects if p.get('batch_id') == batch_id]
            if policy.get('unit', b['unit']) != b['unit'] and any(cost_entries(p) for p in members):
                raise StudioError('cost_unit_locked', 'Existing batch attempts use the current cost unit.', 409)
            was_auto_retry = b['auto_retry']
            b.update(policy, revision=b['revision'] + 1)
            for p in members:
                r = p['production']['resources']
                for key in ['unit', 'image_cost', 'video_cost', 'cost_evidence']:
                    if key in policy:
                        r[key] = policy[key]
                if b['auto_retry'] and not was_auto_retry:
                    p['production']['require_recorded_checks'] = True
                    self._reopen(p, 'visual_direction')
                p['revision'] += 1
                self._progress(p)
                from .creator_chat import current_decision, append_decision
                if current_decision():
                    append_decision(p, current_decision())
                conn.execute('UPDATE studio_projects SET payload=? WHERE id=?', (json.dumps(p), p['id']))
            conn.execute('UPDATE studio_batches SET payload=? WHERE id=?', (json.dumps(b), batch_id))
        return b

    def set_project_dispatch(self, project_id, paused, priority, expected_revision):
        if type(paused) is not bool or type(priority) is not int or not -100 <= priority <= 100:
            raise StudioError('invalid_dispatch', 'Use a pause toggle and integer priority from -100 to 100.')
        def update(p):
            p['dispatch'] = {'paused': paused, 'priority': priority, 'blocked_reason': ''}
            from .creator_chat import current_decision
            decision = current_decision()
            p['history'].append({'at': utc(), 'type': 'dispatch_policy', 'actor': decision['actor'] if decision else 'user', 'message': 'Project paused' if paused else 'Project queued; blocked note cleared'})
        return self.mutate(project_id, expected_revision, update)

    def _batch_metrics(self, batch, projects):
        members = [p for p in projects if p.get('batch_id') == batch['id']]
        jobs = [j for p in members for j in cost_entries(p)]
        units = {j.get('cost', {}).get('unit', batch['unit']) for j in jobs}
        grouped = {unit: total([j for j in jobs if j.get('cost', {}).get('unit', batch['unit']) == unit]) for unit in sorted(units)}
        return {**batch, 'reserved_or_spent': grouped.get(batch['unit'], 0), 'costs_by_unit': grouped,
                'other_cost_units': sorted(units - {batch['unit']}), 'unknown_cost_jobs': sum(exposure(j) is None for j in jobs),
                'active_jobs': sum(j.get('status') in ['awaiting_external_output', 'queued', 'running'] for j in jobs),
                'failures': sum(j.get('status') in ['failed', 'interrupted'] for j in jobs),
                'reported_defects': sum(bool(a.get('review', {}).get('defect')) for p in members for a in p['assets'])}
