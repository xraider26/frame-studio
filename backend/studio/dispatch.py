"""Durable agent work leases and real multi-project queue state."""
import copy
import json
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from .batching import utc, checked_text
from .store import StudioError, load
from .resources import total, exposure

ACTIVE = ['awaiting_external_output', 'queued', 'running']


def expiry():
    return (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()


def progress_hash(p):
    substantive = {k: p.get(k) for k in ['settings', 'production', 'documents', 'shots', 'assets', 'jobs', 'steps', 'shared_identity']}
    return hashlib.sha256(json.dumps(substantive, sort_keys=True).encode()).hexdigest()


class Dispatch:
    def _dispatch_block(self, p, kind=None, existing_job=None, include_leases=True, projects=None, batch=None, lease_project_ids=None):
        dispatch = p.get('dispatch', {})
        if dispatch.get('paused'):
            return 'This project is paused. Resume it in the production queue.'
        if dispatch.get('blocked_reason'):
            return 'Agent needs attention: ' + dispatch['blocked_reason']
        if not p.get('batch_id'):
            return None
        batch = batch or self.get_batch(p['batch_id'])
        if batch['paused']:
            return 'This production batch is paused.'
        projects = [q if q['id'] != p['id'] else p for q in (projects if projects is not None else self.all()) if q.get('batch_id') == batch['id']]
        occupied = {q['id'] for q in projects if any(j['status'] in ACTIVE for j in q['jobs'])}
        if include_leases:
            active_ids = {q['id'] for q in projects if not q.get('deleted_at')}
            if lease_project_ids is None:
                with self.connect() as conn:
                    lease_project_ids = {r[0] for r in conn.execute("SELECT project_id FROM studio_tasks WHERE status='active' AND expires_at>?", (utc(),))}
            occupied.update(set(lease_project_ids) & active_ids)
        if p['id'] not in occupied and len(occupied) >= batch['max_parallel']:
            return 'Batch parallel-project limit is in use. Wait for an active item to finish.'
        if kind and batch['budget_limit'] is not None:
            jobs = [j for q in projects for j in q['jobs']]
            if any(q['production']['resources']['unit'] != batch['unit'] for q in projects) or any(j.get('cost', {}).get('unit', batch['unit']) != batch['unit'] for j in jobs):
                return 'Batch budget needs one consistent cost unit.'
            price = p['production']['resources'][kind + '_cost']
            if any(exposure(j) is None for j in jobs) or (not existing_job and (price is None or not p['production']['resources']['cost_evidence'])):
                return 'A hard batch budget needs evidenced planned costs and known/reserved amounts for earlier jobs.'
            addition = 0 if existing_job else price
            if Decimal(str(total(jobs))) + Decimal(str(addition or 0)) > Decimal(str(batch['budget_limit'])):
                return 'Batch budget would be exceeded. Review costs and the batch limit.'
        return None

    def _queue_item(self, p, leases, projects=None, batch=None):
        action = self._next(p)
        lease = leases.get(p['id'])
        active_jobs = [j for j in p['jobs'] if j['status'] in ACTIVE]
        gate = self._dispatch_block(p, action.get('kind') if action['action'] == 'generate' else None, projects=projects, batch=batch, lease_project_ids=set(leases))
        actionable = action['action'] in ['prepare_step', 'prepare_shots', 'write_prompt', 'record_quality', 'resolve_preflight', 'generate']
        if p.get('dispatch', {}).get('paused') or (p.get('batch_id') and (batch or self.get_batch(p['batch_id']))['paused']):
            state, actionable = 'paused', False
        elif lease:
            state, actionable = 'working', False
        elif active_jobs:
            state, actionable = 'waiting_output', False
        elif action['action'] == 'complete':
            state, actionable = 'complete', False
        elif action['action'] == 'await_approval':
            state, actionable = 'awaiting_approval', False
        elif gate:
            state, actionable = 'attention', False
        elif action['action'] in ['quality_attention', 'resolve_resources']:
            state, actionable = 'attention', False
        elif action['action'] == 'resolve_preflight':
            state = 'attention'
        else:
            state = 'ready'
        return {'project_id': p['id'], 'project_name': p['name'], 'revision': p['revision'], 'batch_id': p.get('batch_id'),
                'dispatch_paused': p.get('dispatch', {}).get('paused', False),
                'priority': p.get('dispatch', {}).get('priority', 0), 'state': state, 'actionable': actionable, 'next_action': action,
                'message': gate or action['message'], 'lease': lease, 'active_jobs': len(active_jobs),
                'reserved_or_spent': total(p['jobs']), 'unknown_cost_jobs': sum(exposure(j) is None for j in p['jobs']),
                'unit': p['production']['resources']['unit'], 'failures': sum(j['status'] in ['failed', 'interrupted'] for j in p['jobs']),
                'identity_version': p.get('shared_identity', {}).get('version', 0),
                'quality_retries': sum(sum(s.get('quality_retries', {}).values()) for s in p['shots'])}

    def production_queue(self, batch_id=None):
        all_projects = self.all()
        projects = [p for p in all_projects if not p.get('deleted_at') and (not batch_id or p.get('batch_id') == batch_id)]
        batches = self.list_batches()
        by_id = {b['id']: b for b in batches}
        with self.connect() as conn:
            leases = {r[0]: json.loads(r[1]) for r in conn.execute("SELECT project_id,payload FROM studio_tasks WHERE status='active' AND expires_at>?", (utc(),))}
        rows = [self._queue_item(p, leases, projects=all_projects, batch=by_id.get(p.get('batch_id'))) for p in projects]
        rows.sort(key=lambda r: (-r['priority'], r['project_name'], r['project_id']))
        return {'items': rows, 'batches': [self._batch_metrics(b, all_projects) for b in batches if not batch_id or b['id'] == batch_id],
                'instructions': 'Connect your agent through MCP. Claim a queue task, read its actual next action, prepare documents or claim_generation and return real media, record inspections, then finish the lease. Renew long tasks. Approval waits belong to the user.'}

    def claim_queue_task(self, actor, request_id, batch_id=None):
        key = checked_text(actor, 100, True) + ':' + checked_text(request_id, 200, True)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            retried = conn.execute('SELECT status,expires_at,payload FROM studio_tasks WHERE request_key=?', (key,)).fetchone()
            if retried:
                task = json.loads(retried[2])
                task['status'] = 'expired' if retried[0] == 'active' and retried[1] <= utc() else retried[0]
                if task['status'] != 'active':
                    task['instructions'] = 'This lease is closed or expired. Do not execute its old task context. Read the queue and use a new request_id to claim fresh work.'
                return task
            conn.execute("UPDATE studio_tasks SET status='expired' WHERE status='active' AND expires_at<=?", (utc(),))
            leases = {r[0]: json.loads(r[1]) for r in conn.execute("SELECT project_id,payload FROM studio_tasks WHERE status='active'")}
            projects = [load(r[0]) for r in conn.execute('SELECT payload FROM studio_projects')]
            projects = [p for p in projects if not p.get('deleted_at') and (not batch_id or p.get('batch_id') == batch_id)]
            projects.sort(key=lambda p: (-p.get('dispatch', {}).get('priority', 0), p['created_at'], p['id']))
            for p in projects:
                row = self._queue_item(p, leases)
                if not row['actionable']:
                    continue
                task = {'id': uuid.uuid4().hex, 'project_id': p['id'], 'batch_id': p.get('batch_id'), 'actor': actor,
                        'project_revision': p['revision'], 'created_at': utc(), 'expires_at': expiry(), 'status': 'active',
                        'progress_hash': progress_hash(p),
                        'next_action': row['next_action'], 'idea_request': p.get('idea_request'), 'identity_contract': p.get('shared_identity'),
                        'instructions': 'Read get_project and follow next_action. Use actual documents and authorized generation tools; claim_generation returns exact prompts and file return contract. Record real media inspection. Do not approve user gates. Finish this lease after progress or block it with the actual reason; renew before expiry.'}
                conn.execute('INSERT INTO studio_tasks VALUES (?,?,?,?,?,?)', (task['id'], p['id'], key, 'active', task['expires_at'], json.dumps(task)))
                return task
        return {'id': None, 'status': 'idle', 'message': 'No dispatchable work: active workers, output waits, approval gates, pauses and limits are respected.'}

    def _owned_task(self, conn, task_id, actor):
        row = conn.execute('SELECT status,expires_at,payload FROM studio_tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise StudioError('task_not_found', 'Queue task not found.', 404)
        task = json.loads(row[2])
        if task['actor'] != actor:
            raise StudioError('task_owner', 'Only the claiming agent may finish or renew this task.', 403)
        if row[0] != 'active' or row[1] <= utc():
            raise StudioError('task_expired', 'This lease is closed or expired. Claim fresh work before proceeding.', 409)
        return task

    def renew_queue_task(self, task_id, actor):
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            task = self._owned_task(conn, task_id, actor)
            task['expires_at'] = expiry()
            conn.execute('UPDATE studio_tasks SET expires_at=?,payload=? WHERE id=?', (task['expires_at'], json.dumps(task), task_id))
        return task

    def finish_queue_task(self, task_id, actor, status, note=''):
        if status not in ['done', 'blocked']:
            raise StudioError('invalid_task_status', 'Finish a queue task as done or blocked.')
        note = checked_text(note, 2000, status == 'blocked')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            task = self._owned_task(conn, task_id, actor)
            row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (task['project_id'],)).fetchone()
            p = load(row[0])
            if status == 'done' and (p['revision'] <= task['project_revision'] or progress_hash(p) == task.get('progress_hash')):
                raise StudioError('no_task_progress', 'No project changes were recorded. Perform the real work or report why it is blocked.', 409)
            if status == 'blocked':
                p.setdefault('dispatch', {}).update(blocked_reason=note)
                p['revision'] += 1
                conn.execute('UPDATE studio_projects SET payload=? WHERE id=?', (json.dumps(p), p['id']))
            task.update(status=status, note=note, completed_at=utc())
            conn.execute('UPDATE studio_tasks SET status=?,payload=? WHERE id=?', (status, json.dumps(task), task_id))
        return task
