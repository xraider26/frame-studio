"""Explicit creator instructions relayed by a connected chat client.

This is an attributed conversational decision, not proof of a browser click.
Ordinary agent operations retain their existing permissions.
"""
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json

_decision = ContextVar('orchestra_creator_decision', default=None)
_connection = ContextVar('orchestra_creator_connection', default=None)

OPERATIONS = {
    'request_revision', 'review_calibration', 'set_calibration_mode', 'configure_calibration',
    'review', 'set_policy', 'select_take', 'update_settings', 'update_shots', 'update_production',
    'set_generation_setup', 'apply_sequence', 'activate_recipe', 'apply_project_template',
    'delete_project', 'restore_project', 'save_project_template', 'rename_project_template',
    'delete_project_template', 'set_project_dispatch', 'sync_batch_identity', 'record_recipe_trial',
    'save_connection', 'validate_connection', 'export_comfy_handoff', 'update_batch', 'endorse_recipe',
    'import_reference',
}


def current_decision():
    return _decision.get()


def current_connection(path):
    active = _connection.get()
    return active[1] if active and active[0] == str(path.resolve()) else None


def creator_authority(actor):
    current = current_decision()
    return actor == 'user' or bool(current and actor == current['actor'])


def prepare_decision(payload, client):
    from .store import StudioError
    from .agent_rules import validate_revision
    required = {'project_id', 'expected_revision', 'request_id', 'user_instruction', 'operation', 'arguments'}
    if not isinstance(payload, dict) or set(payload) != required:
        raise StudioError('invalid_creator_decision', 'Provide project, revision, request_id, exact user_instruction, operation and arguments.')
    validate_revision(payload['expected_revision'])
    for field, maximum in [('project_id', 200), ('request_id', 200), ('user_instruction', 8000)]:
        if not isinstance(payload[field], str) or not payload[field].strip() or len(payload[field]) > maximum:
            raise StudioError('invalid_creator_decision', 'A nonempty '+field+' is required.')
    if not isinstance(payload['operation'], str) or payload['operation'] not in OPERATIONS or not isinstance(payload['arguments'], dict):
        raise StudioError('invalid_creator_decision', 'Choose a supported creator decision operation.')
    arguments = copy.deepcopy(payload['arguments'])
    if any(k in arguments for k in ['actor', 'user_instruction', 'expected_revision']):
        raise StudioError('invalid_creator_decision', 'Decision authority and revision belong to the outer request.')
    if arguments.get('project_id', payload['project_id']) != payload['project_id']:
        raise StudioError('invalid_creator_decision', 'The decision must target its named project.')
    try:
        fingerprint = hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k != 'expected_revision'}, sort_keys=True, allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError) as exc:
        raise StudioError('invalid_creator_decision', 'Decision arguments must be finite JSON data.') from exc
    return {**copy.deepcopy(payload), 'fingerprint': fingerprint,
            'actor': 'creator_chat:'+client[:80], 'relayed_by': 'agent:'+client[:94],
            'authority': 'user_instruction_relayed', 'source': 'chat',
            'recorded_at': datetime.now(timezone.utc).isoformat()}


def prior_decision(project, decision):
    from .store import StudioError
    old = next((d for d in project.get('creator_decisions', []) if d['request_id'] == decision['request_id']), None)
    if old and old['fingerprint'] != decision['fingerprint']:
        raise StudioError('decision_conflict', 'This request_id already records a different creator instruction.', 409)
    return old


def decision_project(studio, project_id):
    from .store import load, StudioError
    with studio.connect() as conn:
        row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (project_id,)).fetchone()
    if not row:
        raise StudioError('not_found', 'Project not found.', 404)
    return load(row[0])


def append_decision(project, decision):
    record = {k: decision[k] for k in ['request_id', 'operation', 'user_instruction', 'expected_revision',
              'fingerprint', 'actor', 'relayed_by', 'authority', 'source', 'recorded_at']}
    record['target'] = {k: v for k, v in decision['arguments'].items() if k in {'asset_id', 'shot_id', 'step', 'kind'}}
    record['project_id'] = decision['project_id']
    record['affected_project_id'] = project['id']
    project.setdefault('creator_decisions', []).append(record)
    project['history'].append({'at': record['recorded_at'], 'type': 'creator_decision', 'actor': record['actor'],
                               'message': 'Chat instruction applied: '+record['operation'],
                               'source': 'chat', 'relayed_by': record['relayed_by']})


def decision_response(studio, decision, result=None, *, save_result=False):
    from .store import load
    def summary(value):
        if isinstance(value, dict):
            keys = {'id', 'revision', 'name', 'kind', 'version', 'url', 'download_url', 'status', 'deleted_at', 'width', 'height'}
            return {k:copy.deepcopy(v) for k,v in value.items() if k in keys}
        if isinstance(value, list):
            return [summary(item) for item in value]
        return value if isinstance(value, (str, int, float, bool)) or value is None else None
    with studio.connect() as conn:
        row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (decision['project_id'],)).fetchone()
        project = load(row[0])
        receipt = prior_decision(project, decision)
        if save_result:
            receipt['result'] = summary(result)
            conn.execute('UPDATE studio_projects SET payload=? WHERE id=?', (json.dumps(project), project['id']))
    return {'project_id': project['id'], 'revision': project['revision'], 'decision': receipt,
            'result': receipt.get('result'),
            'next_action': {'action':'project_deleted'} if project.get('deleted_at') else studio.next_action(project['id'])}


@contextmanager
def decision_scope(decision, studio):
    from .store import StudioError
    providers = []
    decision['provider_writes'] = providers
    try:
        with studio.connect() as conn:
            if not conn.in_transaction:
                conn.execute('BEGIN IMMEDIATE')
            connection_token = _connection.set((str(studio.db_path.resolve()), conn))
            token = _decision.set(decision)
            try:
                project = decision_project(studio, decision['project_id'])
                decision['replayed'] = bool(prior_decision(project, decision))
                if not decision['replayed'] and project['revision'] != decision['expected_revision']:
                    raise StudioError('revision_conflict', 'Refresh before applying this creator instruction.', 409)
                yield decision
                # Provider saves are fixed-key, idempotent file replacements.
                # Defer them until the operation and its audit both validate.
                for provider, _ in providers:
                    provider._save(immediate=True)
            finally:
                _decision.reset(token)
                _connection.reset(connection_token)
    except BaseException:
        for provider, old in providers:
            provider.connections = json.loads(old) if old is not None else {}
            if old is None:
                provider.config_path.unlink(missing_ok=True)
            else:
                provider._save(immediate=True)
        raise
