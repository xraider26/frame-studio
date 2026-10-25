"""Deterministic rule bindings and exact, attributed generation request evidence.

Mappings establish traceability, never media compliance or creator approval.
"""
import copy
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

from .store import StudioError

PROMPT_BINDINGS = {
    'appearance': ['subject', 'environment', 'style', 'palette'],
    'framing': ['framing', 'lens', 'composition', 'camera'], 'light': ['lighting'],
    'motion': ['motion', 'camera', 'opening', 'ending'], 'state': ['continuity', 'state_before', 'state_after'],
    'podcast': ['dialogue', 'sound', 'continuity'],
    'animation': ['style', 'palette', 'motion'], 'clay': ['style', 'motion'],
}
PLANNING_BINDINGS = {
    'brief': ['production.brief', 'documents.brief.text'], 'hook': ['production.story'],
    'timing': ['effective_direction.sound', 'duration_seconds'],
    'claims': ['production.brief.factual_sources'],
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()



def has_content(value):
    """Empty nested planning records do not constitute a concrete binding."""
    if isinstance(value, str): return bool(value.strip())
    if isinstance(value, dict): return any(has_content(item) for item in value.values())
    if isinstance(value, list): return any(has_content(item) for item in value)
    return value is not None


def build_rule_application(project: dict, shot: dict, kind: str, stage: str) -> list[dict]:
    from .recipes import recipe_context
    from .creative import effective_direction
    from .calibration import scoped_requirements, calibration_review_scope, requirement_assets
    context = recipe_context(project, shot)
    if not context.get('active'):
        return []
    direction = effective_direction(project, shot)
    requirements = scoped_requirements(project, shot, kind, calibration_only=calibration_review_scope(project, shot, kind))
    rows = []
    prepared = None
    for rule in context.get('source_rules', []):
        predicate = copy.deepcopy(rule.get('predicate', {'kind': 'always'}))
        pred_kind = predicate.get('kind')
        relevant = [r for r in requirements if r['purpose'] in predicate.get('purposes', [])]
        if pred_kind == 'always': applicable, reason = True, 'Applies to this recipe.'
        elif pred_kind == 'video': applicable, reason = kind == 'video', 'Video-only rule; actual requested medium is '+kind+'.'
        elif pred_kind == 'video_continuity':
            position = next((i for i, item in enumerate(project['shots']) if item['id'] == shot['id']), 0)
            tracked = any(direction['action'].get(key) for key in ('state_before', 'state_after', 'continuity_from'))
            applicable = kind == 'video' and (position > 0 or tracked)
            reason = 'Later shots or explicit mutable states require a continuity binding.' if applicable else 'Initial scene has no preceding shot or explicitly tracked mutable continuity state; no prior state to carry.'
        elif pred_kind == 'reference_purposes':
            applicable = any(r['required'] or requirement_assets(project, shot, r) for r in relevant)
            reason = 'Saved fidelity requirements and actual bound references determine applicability.'
        else: applicable, reason = None, 'Unknown applicability predicate; cannot waive this rule.'
        if rule.get('role_ids') and direction.get('recipe_role') not in rule['role_ids']:
            applicable, reason = False, 'The saved shot role is outside this rule scope.'
        phase = rule.get('phase', 'pre_generation')
        bindings, missing = [], ''
        ident = rule['id']
        if applicable:
            if phase == 'media_review' and ident in {'inspection', 'iteration', 'learning'}:
                from .production import criteria_for
                checks = criteria_for(project, shot, kind)
                bindings = [{'type': 'review_criterion', 'criterion': c} for c in dict.fromkeys(checks)]
            elif phase == 'media_review':
                missing = 'No concrete media-review mapping is implemented for this rule.'
            elif phase == 'external_edit' and ident in {'edit', 'final'}:
                bindings = [{'type': 'external_edit', 'path': 'recipe_contract.stages.'+('final_review' if ident == 'final' else 'editor_handoff'), 'requirements': context.get('stages', {}).get('final_review' if ident == 'final' else 'editor_handoff', [])}]
            elif ident == 'identity':
                missing = ', '.join(r['purpose'] for r in relevant if r['required'] and not requirement_assets(project, shot, r))
                bindings = [{'type': 'reference', 'asset_id': a['id'], 'version': a.get('version', 1), 'slot': a['slot'], 'purpose': r['purpose']} for r in relevant for a in requirement_assets(project, shot, r)]
            elif ident == 'capabilities':
                caps = project['production'].get('capabilities_by_kind', {}).get(kind, {}) if project.get('generation_setup') else project['production']['capabilities']
                if caps.get('confirmed') and caps.get('source') and caps.get('observed_at') and caps.get('model'):
                    bindings = [{'type': 'prerequisite', 'path': 'production.capabilities_by_kind.'+kind if project.get('generation_setup') else 'production.capabilities', 'observation': copy.deepcopy(caps)}]
                else: missing = 'Actual generator capabilities have not been verified.'
            elif ident in PROMPT_BINDINGS:
                from .generators import prompt_for
                if prepared is None: prepared = prompt_for(project, shot, kind)
                bindings = [{'type': 'prompt_field', 'path': 'compiled_fields.'+field, 'value': copy.deepcopy(prepared['compiled_fields'][field])}
                            for field in PROMPT_BINDINGS[ident] if field in prepared['template_fields'] and has_content(prepared['compiled_fields'][field])]
                if ident == 'state':
                    # Aggregate continuity also contains appearance/bible prose. Only
                    # actual populated mutable-state inputs can ground this rule.
                    contributions = [{'path': 'effective_direction.action.'+field, 'value': copy.deepcopy(direction['action'][field])}
                                     for field in ('state_before', 'state_after') if has_content(direction['action'][field])]
                    bindings = []
                    for field in PROMPT_BINDINGS['state']:
                        carried = contributions if field == 'continuity' else [c for c in contributions if c['path'].endswith('.'+field)]
                        if carried and field in prepared['template_fields'] and has_content(prepared['compiled_fields'][field]):
                            bindings.append({'type': 'prompt_field', 'path': 'compiled_fields.'+field, 'value': copy.deepcopy(prepared['compiled_fields'][field]), 'state_contributions': carried})
                if kind == 'image' and direction['image']['mode'] == 'edit':
                    # Source-image appearance is bound through actual refs; unused recipe defaults are not edits.
                    if ident in {'appearance', 'framing', 'light'}:
                        from .preflight import references_for
                        bindings = [{'type': 'reference', 'asset_id': r['id'], 'version': r.get('version', 1), 'slot': r['slot']} for r in references_for(project, shot, kind)]
                if not bindings: missing = 'This rule has no populated field in the actual prompt template or bound edit source.'
            elif ident in PLANNING_BINDINGS:
                for path in PLANNING_BINDINGS[ident]:
                    root = {'production': project['production'], 'documents': project.get('documents', {}), 'effective_direction': direction, 'duration_seconds': shot['duration_seconds']}
                    value = root
                    for key in path.split('.'): value = value.get(key) if isinstance(value, dict) else None
                    if has_content(value): bindings.append({'type': 'prompt_field', 'path': path, 'value': copy.deepcopy(value), 'destination': 'separate_notes'})
                if not bindings: missing = 'No populated planning source is recorded for this rule.'
            else: missing = 'No concrete mapping is implemented for this rule.'
        status = 'not_applicable' if applicable is False else ('applied' if applicable and bindings and not missing else 'unverified')
        # Multiple purposes may bind the same actual asset; retain each distinct purpose once.
        bindings = list({json.dumps(b, sort_keys=True): b for b in bindings}.values())
        rows.append({'rule_id': ident, 'rule_version': rule.get('version', 1), 'source_id': rule.get('source_id'),
            'source_locator': rule.get('section'), 'provenance': rule.get('provenance', 'review_derived'),
            'original_page_citations': copy.deepcopy(rule.get('citations', [])),
            'studio_correction': {'text': rule.get('correction', ''), 'provenance': 'studio_correction', 'citations': copy.deepcopy(rule.get('correction_citations', []))},
            'citation_scope': rule.get('citation_scope', ''), 'required': rule.get('required', False),
            'phase': phase, 'stage': copy.deepcopy(rule.get('stage', ['visual_direction', 'pilot', 'production'])),
            'role_ids': copy.deepcopy(rule.get('role_ids', [])), 'predicate': predicate,
            'predicate_result': {'applicable': applicable, 'reason': reason, 'scope': copy.deepcopy(relevant)},
            'status': status, 'reason': missing or reason, 'bindings': bindings,
            'outcome': 'pending' if phase in {'media_review', 'external_edit'} and applicable else None})
    return rows


def rule_blockers(rows, stage):
    return [r for r in rows if r['required'] and r['status'] != 'not_applicable'
            and ((r['phase'] in {'pre_generation', 'media_review'} and stage in r['stage']) or (r['phase'] == 'external_edit' and stage in r['stage']))
            and (r['status'] != 'applied' or not r['bindings'])]


def reference_manifest(refs):
    return [{k: r.get(k) for k in ('id', 'version', 'slot')} for r in refs]


def normalize_lines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def validate_execution(job: dict, execution: dict) -> dict:
    handoff = job.get('handoff', {})
    available = isinstance(execution, dict) and all(k in execution for k in ('prompt', 'negative_prompt', 'references'))
    prompt = 'unavailable'; refs = 'unavailable'
    if available:
        prompt = 'match' if all(isinstance(execution[k], str) and normalize_lines(execution[k]) == normalize_lines(handoff.get(k, '')) for k in ('prompt', 'negative_prompt')) else 'mismatch'
        refs = 'match' if reference_manifest(execution['references']) == reference_manifest(handoff.get('references', [])) else 'mismatch'
        arguments = execution.get('arguments', {})
        if isinstance(arguments, dict):
            # Native tool arguments are authoritative when their schema is known.
            if isinstance(arguments.get('prompt'), str) and normalize_lines(arguments['prompt']) != normalize_lines(execution['prompt']): prompt = 'mismatch'
            if isinstance(arguments.get('negative_prompt'), str) and normalize_lines(arguments['negative_prompt']) != normalize_lines(execution['negative_prompt']): prompt = 'mismatch'
            if 'referenced_image_paths' in arguments and (execution.get('reference_files') is not None or arguments['referenced_image_paths'] != [r.get('path') for r in handoff.get('references', [])]):
                # A client may stage the same versioned bytes outside AppData.
                # Keep native arguments exact and compare separately observed
                # file digests; a claimed alternate path alone is insufficient.
                observed = execution.get('reference_files', [])
                expected = handoff.get('references', [])
                try:
                    paths = arguments['referenced_image_paths']
                    identical = (isinstance(paths, list) and len(paths) == len(expected) == len(observed)
                                 and [f['path'] for f in observed] == paths)
                    for actual, reference in zip(observed, expected):
                        with Path(reference['path']).open('rb') as stream:
                            identical = identical and actual.get('sha256') == hashlib.file_digest(stream, 'sha256').hexdigest()
                    if not identical: refs = 'mismatch'
                except (OSError, KeyError, TypeError):
                    refs = 'mismatch'
        if execution.get('tool') in {'imagegen', 'image_gen', 'image_gen.imagegen'} and execution['negative_prompt']:
            # An unsupported native field cannot be made applied by reporting it separately.
            prompt = 'mismatch'

    return {'state': 'unavailable' if not available else ('match' if prompt == refs == 'match' else 'mismatch'),
            'prompt_match': prompt, 'references_match': refs, 'evidence_source': execution.get('evidence_source', 'agent_reported') if available else 'unavailable',
            'contract_status': 'versioned' if handoff.get('execution_contract') else 'legacy_unavailable',
            'comparison': 'Exact text with line-ending normalization only; no semantic equivalence or media quality claim.'}


def execution_contract(prepared, refs, selection):
    """Describe compiler requirements without inventing unsupported native arguments."""
    managed_image = selection and (selection.get('executor') == 'agent_builtin' or selection.get('tool_name') in {'imagegen', 'image_gen', 'image_gen.imagegen'})
    unsupported = []
    if managed_image:
        if prepared['negative_prompt']: unsupported.append({'field': 'negative_prompt', 'value': prepared['negative_prompt'], 'reason': 'This tool exposes no separate negative argument; revise saved inputs explicitly before changing the prompt.'})
        if prepared.get('model'): unsupported.append({'field': 'model', 'value': prepared['model'], 'reason': 'This tool exposes no model argument.'})
    return {'version': 1, 'compiled_prompt': prepared['prompt'], 'compiled_negative_prompt': prepared['negative_prompt'],
            'references': reference_manifest(refs), 'generator_selection': copy.deepcopy(selection),
            'unsupported_constraints': unsupported, 'required_evidence': ['tool', 'prompt', 'negative_prompt', 'references', 'arguments'],
            'instructions': 'Record the actual submitted request and reference versions. Preserve compiler content exactly; material changes require revised saved inputs and a new claim. Unavailable constraints must remain disclosed.'}


class ExecutionEvidence:
    def record_generation_execution(self, job_id: str, execution: dict, expected_revision: int, actor: str) -> dict:
        from .agent_rules import validate_revision
        validate_revision(expected_revision)
        return self._record_generation_execution(job_id, execution, expected_revision, actor, server=False)

    def _record_generation_execution(self, job_id, execution, expected_revision, actor, *, server=False):
        allowed = {'tool', 'prompt', 'negative_prompt', 'references', 'arguments', 'unsupported_constraints', 'reference_files'}
        if not isinstance(execution, dict) or set(execution)-allowed or not {'tool','prompt','negative_prompt','references','arguments'} <= execution.keys():
            raise StudioError('invalid_execution', 'Provide exact tool, positive/negative prompts, actual references and supplied arguments; attribution is server controlled.')
        if any(not isinstance(execution[k], str) or len(execution[k]) > 100000 for k in ('tool','prompt','negative_prompt')) or not execution['tool'].strip() or not isinstance(execution['references'], list) or len(execution['references']) > 100 or not isinstance(execution['arguments'], dict):
            raise StudioError('invalid_execution', 'Execution request fields have invalid types or sizes.')
        if any(not isinstance(r, dict) or not isinstance(r.get('id'), str) or type(r.get('version')) is not int or r['version'] < 1 or not isinstance(r.get('slot'), str) for r in execution['references']):
            raise StudioError('invalid_execution', 'Every submitted reference needs its actual asset ID, integer version and slot.')
        files = execution.get('reference_files', [])
        if not isinstance(files, list) or len(files) > 100 or any(not isinstance(f, dict) or set(f) != {'path', 'sha256'} or not isinstance(f['path'], str) or not isinstance(f['sha256'], str) or len(f['sha256']) != 64 for f in files):
            raise StudioError('invalid_execution', 'Observed reference files need their submitted local path and SHA256.')
        try: size = len(json.dumps(execution, allow_nan=False))
        except (TypeError, ValueError) as exc: raise StudioError('invalid_execution', 'Execution must be finite JSON data.') from exc
        if size > 2_000_000: raise StudioError('invalid_execution', 'Execution evidence exceeds 2 MB.')
        project, _ = self.find_job(job_id)
        def update(p):
            job = next(j for j in p['jobs'] if j['id'] == job_id)
            if not server and job['actor'] != actor: raise StudioError('job_owner', 'Only this job owner may report its actual execution.', 403)
            if job['status'] in {'canceled', 'failed', 'interrupted'}: raise StudioError('job_closed', 'This job is closed.', 409)
            request = copy.deepcopy(execution); request_hash = digest(request)
            if job.get('execution'):
                if job['execution']['request_hash'] != request_hash: raise StudioError('execution_immutable', 'A submitted request cannot be overwritten. Revise inputs and claim a new job.', 409)
                return copy.deepcopy(job['execution'])
            request.update(evidence_source='server_recorded' if server else 'agent_reported', actor=actor,
                recorded_at=datetime.now(timezone.utc).isoformat(), request_hash=request_hash)
            request['validation'] = validate_execution(job, request)
            job['execution'] = request
            if job.get('asset_id'):
                asset = next(a for a in p['assets'] if a['id'] == job['asset_id'])
                asset['execution_validation'] = copy.deepcopy(request['validation'])
                asset['execution_state'] = 'match' if request['validation']['state'] == 'match' else 'needs_review'
                job['status'] = ('succeeded_stale' if asset.get('stale') else 'succeeded') if asset['execution_state'] == 'match' else 'needs_review'
            self._progress(p)
            return copy.deepcopy(request)
        return self.mutate(project['id'], expected_revision, update)
