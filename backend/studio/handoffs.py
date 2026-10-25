"""Transport views over immutable generation evidence; never authorization."""
import copy
import hashlib
import json

from .store import StudioError

MAX_PAYLOAD_BYTES = 64 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def byte_size(value):
    return len(encoded(value))


def content_version(value):
    return 'sha256:' + hashlib.sha256(encoded(value)).hexdigest()


def context_blob(context_id, data):
    return {'context_id': context_id, 'version': content_version(data), 'data': copy.deepcopy(data)}


def check_payload(value):
    size = byte_size(value)
    if size > MAX_PAYLOAD_BYTES:
        fields = {key: byte_size(item) for key, item in value.items()}
        if isinstance(value.get('handoff'), dict):
            fields.update({'handoff.'+key: byte_size(item) for key, item in value['handoff'].items()})
        raise StudioError('payload_too_large', json.dumps({'bytes': size, 'ceiling_bytes': MAX_PAYLOAD_BYTES,
            'field_bytes': fields, 'remedies': ['Fetch shared context with get_context(context_id, version).',
                'Use recipe_catalog/sequence_catalog/source_catalog with ID, stage and role scope.',
                'Explicitly revise oversized saved prompt/reference scope with the creator; required fields are never truncated.',
                'Use get_job(detail="full") for the complete diagnostic snapshot.']}, separators=(',', ':')), 413)
    return value


def recipe_summary(context):
    return {key: copy.deepcopy(context[key]) for key in ('active', 'id', 'name', 'version', 'intent', 'output_type', 'message', 'validation_status') if key in context}


def serialize_capabilities(value, detail='summary'):
    if detail not in {'summary', 'full'}: raise StudioError('invalid_detail', 'Choose summary or full.')
    result = copy.deepcopy(value)
    result['schema_version'] = 3
    if detail == 'summary':
        result.pop('creative_schema', None)
        result.pop('knowledge_coverage', None)
        result['detail_tools'] = ['creative_schema', 'recipe_catalog', 'sequence_catalog', 'source_catalog', 'get_context']
        for key in ('templates', 'image_profiles', 'video_profiles'):
            result[key] = [{k: item[k] for k in ('id', 'name', 'output_type', 'aspect') if k in item} for item in result.get(key, [])]
    return result


def build_execution_packet(project: dict, shot: dict, kind: str, stage: str, contract: dict) -> dict:
    from .recipes import recipe_context
    from .agent_rules import policy_snapshot
    from .sequences import sequence_context
    recipe = recipe_context(project, shot)
    compact_recipe = recipe_summary(recipe)
    if recipe.get('active'):
        compact_recipe.update(stage_instructions=copy.deepcopy(recipe.get('stage_instructions', {}).get(stage, [])),
            shot_role=copy.deepcopy(recipe.get('shot_role')), decision_requirements=copy.deepcopy(recipe.get('decision_requirements', [])))
    blobs = {'recipe': context_blob('recipe:'+project['id'], recipe),
             'production': context_blob('production:'+project['id'], project['production'])}
    sequence = sequence_context(project)
    if sequence: blobs['sequence'] = context_blob('sequence:'+project['id'], sequence)
    return {'source_revision': project['revision'], 'contract_version': contract['contract_version'],
        'rules_version': contract['rules_version'], 'project_policy': policy_snapshot(project),
        'capabilities': copy.deepcopy(project['production'].get('capabilities_by_kind', {}).get(kind, project['production'].get('capabilities'))),
        'recipe_contract': compact_recipe,
        'context_refs': {key: {k: blob[k] for k in ('context_id', 'version')} for key, blob in blobs.items()},
        '_context_blobs': list(blobs.values())}


def serialize_job(job: dict, detail: str = 'summary') -> dict:
    if detail not in {'summary', 'execution', 'full'}: raise StudioError('invalid_detail', 'Choose summary, execution or full.')
    result = copy.deepcopy(job)
    if detail == 'execution':
        result['handoff'] = serialize_claim({'job': job, 'handoff': job.get('handoff', {})})['handoff']
    if detail == 'summary':
        result.pop('handoff', None)
        if result.get('execution'):
            result['execution'] = {key: result['execution'][key] for key in ('tool', 'evidence_source', 'request_hash', 'validation', 'recorded_at') if key in result['execution']}
        result['detail_available'] = True
    return result


def serialize_project(project: dict, detail: str = 'summary') -> dict:
    if detail not in {'summary', 'full'}: raise StudioError('invalid_detail', 'Choose summary or full.')
    result = copy.deepcopy(project)
    result['jobs'] = [serialize_job(job, detail) for job in result.get('jobs', [])]
    if detail == 'summary':
        if result.get('recipe_context'): result['recipe_context'] = recipe_summary(result['recipe_context'])
        if result.get('sequence_context'):
            result['sequence_context'] = {k: result['sequence_context'][k] for k in ('id', 'name', 'description') if k in result['sequence_context']}
    return result


def serialize_claim(result: dict, response_format: str = 'compact') -> dict:
    if response_format == 'legacy': return copy.deepcopy(result)
    if response_format != 'compact': raise StudioError('invalid_response_format', 'Choose compact or legacy.')
    out = copy.deepcopy(result)
    out['schema_version'] = 3
    job = out.get('job')
    if not job: return out
    raw = out.get('handoff', job.get('handoff', {}))
    packet = raw.get('execution_packet', {})
    # Values below remain byte-for-byte strings. Diagnostic compiler/provenance
    # data and unrelated project material are available through targeted reads.
    omitted = {'production', 'recipe_contract', 'compiled_fields', 'prompt_contributions', 'effective_direction', 'model_guidance', 'execution_packet'}
    # Old immutable jobs have no separately captured policy/context packet.
    # Keep their policy and instructions rather than silently dropping them.
    h = {key: copy.deepcopy(value) for key, value in raw.items() if not packet or key not in omitted}
    if not packet and isinstance(h.get('recipe_contract'), dict):
        # Historical coverage is a duplicated bibliography/diagnostic map.
        # Preserve its actual source rules, instructions and production policy.
        h['recipe_contract'].pop('coverage', None)
    h.update({key: copy.deepcopy(value) for key, value in packet.items() if not key.startswith('_')})
    inactive = 'video' if h.get('kind') == 'image' else 'image'
    if isinstance(h.get('creative_settings'), dict):
        h['creative_settings'] = {k: v for k, v in h['creative_settings'].items() if k not in {inactive+'_model', inactive+'_generator', 'custom_'+inactive+'_template', 'creative_intake'}}
    teachings = {r['id']: r.get('teaching') for r in raw.get('recipe_contract', {}).get('source_rules', [])}
    for rule in h.get('rule_application', []):
        # Repeated citation bibliographies are diagnostic provenance, not rule
        # instructions. Keep correction text, source IDs/locators and every
        # applicability, requiredness, binding and unknown field intact.
        for key in ('original_page_citations', 'citation_scope', 'provenance'): rule.pop(key, None)
        if isinstance(rule.get('studio_correction'), dict):
            rule['studio_correction'] = {k: v for k, v in rule['studio_correction'].items() if k not in {'citations', 'provenance'}}
        if rule.get('predicate_result', {}).get('applicable') is not False and teachings.get(rule['rule_id']):
            rule['teaching'] = teachings[rule['rule_id']]
        if rule.get('reason') == rule.get('predicate_result', {}).get('reason'):
            rule.pop('reason', None)  # Same reason remains in predicate_result.
    h.update(schema_version=3, owner=job['actor'], cost=copy.deepcopy(job.get('cost')))
    out.update(job=serialize_job(job), handoff=h)
    out['job'].pop('detail_available', None)
    return check_payload(out)


class ContextReads:
    def _save_contexts(self, blobs, conn=None):
        def save(connection):
            connection.execute('CREATE TABLE IF NOT EXISTS studio_contexts (context_id TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(context_id, version))')
            for blob in blobs:
                connection.execute('INSERT OR IGNORE INTO studio_contexts VALUES (?,?,?)', (blob['context_id'], blob['version'], encoded(blob).decode('utf-8')))
        if conn is not None:
            save(conn)
        else:
            with self.connect() as connection:
                save(connection)

    def get_context(self, context_id: str, version: str) -> dict:
        with self.connect() as conn:
            table = conn.execute("SELECT name FROM sqlite_master WHERE name='studio_contexts'").fetchone()
            row = conn.execute('SELECT payload FROM studio_contexts WHERE context_id=? AND version=?', (context_id, version)).fetchone() if table else None
        if not row: raise StudioError('context_not_found', 'Read current context references; this exact ID/version is unavailable.', 404)
        return json.loads(row[0])
