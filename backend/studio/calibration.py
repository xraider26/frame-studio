"""Creator-owned visual baselines and purpose-scoped technical evidence.

All permissions are computed from current inputs. Stored technical passes never
confer creator authority, and decision history is retained when inputs change.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .store import StudioError
from .creative import effective_direction
from .preflight import references_for, preflight
from .generators import prompt_for

PURPOSES = ('style', 'identity', 'product', 'layout')
STYLE_SETTINGS = ('style', 'palette', 'lighting', 'aspect_ratio', 'custom_image_template', 'image_generator', 'image_model')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def default_calibration():
    return {'version': 1, 'mode': 'calibration', 'status': 'not_started',
            'representative_shot_id': None, 'representative_selection_source': 'automatic', 'baseline_asset_id': None,
            'scope': list(PURPOSES), 'history': [], 'shot_acceptances': {}, 'feedback': '', 'pending_decision': None}


def representative(project):
    key = project.get('calibration', {}).get('representative_shot_id')
    if key:
        return next((s for s in project['shots'] if s['id'] == key), None)
    return project['shots'][0] if project['shots'] else None


def reference_requirements(project):
    """Explicit fidelity obligations are never weakened by agent assertions."""
    return project['production'].get('reference_requirements', [])


def scoped_requirements(project, shot=None, kind="image", *, calibration_only=False):
    requirements = reference_requirements(project)
    c = project.get('calibration', {})
    if not calibration_only or c.get('mode') != 'calibration' or kind != 'image' or (shot and shot['id'] != (representative(project) or {}).get('id')):
        return requirements
    return [r for r in requirements if r['purpose'] in c.get('scope', PURPOSES)]


def calibration_review_scope(project, shot, kind='image'):
    return bool(project.get('calibration', {}).get('mode') == 'calibration' and kind == 'image'
                and shot['id'] == (representative(project) or {}).get('id')
                and calibration_state(project)['status'] != 'approved')


def requirement_assets(project, shot, requirement):
    refs = references_for(project, shot, 'image')
    entities = {e['id']: e for e in project['production']['bible']}
    ids = set(requirement.get('asset_ids', [])) | set(entities.get(requirement.get('entity_id'), {}).get('asset_ids', []))
    roles = {'style': {'style'}, 'identity': {'character'}, 'product': {'prop'}, 'layout': {'location'}}[requirement['purpose']]
    return [a for a in refs if not a.get('stale') and a.get('kind') == 'image' and Path(a.get('path', '')).is_file()
            and (a['id'] in ids or (not ids and a.get('binding_role') in roles and (not requirement.get('entity_id') or a.get('entity_id') == requirement['entity_id'])))]


def missing_references(project, shot, kind="image", *, calibration_only=False):
    return [r for r in scoped_requirements(project, shot, kind, calibration_only=calibration_only) if r['required'] and not requirement_assets(project, shot, r)]


def style_contract_signature(project):
    c = project.get('calibration', {})
    d = project['production']['defaults']
    # Include actual registered style/reference versions; new scene prose is deliberately absent.
    refs = [a for a in project['assets'] if a.get('role') == 'reference' and a.get('kind') == 'image' and not a.get('source_video')]
    image = (project.get('generation_setup') or {}).get('image') or {}
    return digest({'settings': {k: project['settings'].get(k) for k in STYLE_SETTINGS},
                   'intake_style': project['settings'].get('creative_intake', {}).get('art_style'),
                   'shared': {k: d[k] for k in ('art', 'lighting', 'references', 'quality')},
                   'continuity': project.get('shared_identity'), 'bible': project['production']['bible'],
                   'requirements': reference_requirements(project), 'scope': c.get('scope'),
                   'references': [{k: a.get(k) for k in ('id', 'version', 'path')} for a in refs],
                   'image_selection': {k: image.get(k) for k in ('executor', 'tool_name', 'profile', 'model', 'model_version_status', 'connection_id')}})


def baseline_take_signature(project, asset):
    shot = next((s for s in project['shots'] if s['id'] == asset.get('shot_id')), None)
    if not shot:
        return ''
    prepared = prompt_for(project, shot, 'image')
    return digest({'style_contract': style_contract_signature(project), 'asset_id': asset['id'],
                   'asset_version': asset.get('version', 1), 'input_signature': asset.get('input_signature'),
                   'prompt': prepared['prompt'], 'negative': prepared['negative_prompt'], 'requirements': prepared.get('image_requirements'),
                   'references': [{k: a.get(k) for k in ('id', 'slot', 'version', 'binding_role')} for a in references_for(project, shot, 'image')]})


def check_state(value):
    if type(value) is bool:
        return 'pass' if value else 'fail'
    return value.get('state') if isinstance(value, dict) else None


def normalize_review(review):
    data = copy.deepcopy(review)
    data['criteria'] = {k: {'state': 'pass' if v else 'fail', 'reason': ''} if type(v) is bool else v
                        for k, v in data.get('criteria', {}).items()}
    return data


def validate_review_criteria(project, shot, review):
    criteria = review.get('criteria', {})
    if review.get('version', 1) not in (1, 2) or not isinstance(criteria, dict) or len(criteria) > 100:
        raise StudioError('invalid_review', 'Use version 1 booleans or version 2 criterion states.')
    calibration_only = calibration_review_scope(project, shot)
    requirements = scoped_requirements(project, shot, calibration_only=calibration_only)
    required_purposes = {r['purpose'] for r in requirements if r['required']}
    present_purposes = {r['purpose'] for r in requirements if r['required'] or requirement_assets(project, shot, r)}
    for key, value in criteria.items():
        if not isinstance(key, str) or len(key) > 200:
            raise StudioError('invalid_review', 'Criterion names must be text up to 200 characters.')
        state = check_state(value)
        if type(value) is not bool:
            if review.get('version') != 2 or not isinstance(value, dict) or set(value) - {'state', 'reason'} or state not in {'pass', 'fail', 'not_applicable', 'blocked'} or not isinstance(value.get('reason', ''), str) or len(value.get('reason', '')) > 8000:
                raise StudioError('invalid_review', 'Version 2 criteria use pass, fail, not_applicable or blocked and a reason.')
            if state in {'not_applicable', 'blocked'} and not value.get('reason', '').strip():
                raise StudioError('invalid_review', 'Blocked/not-applicable criteria require a reason.')
        if key.startswith('Reference fidelity: '):
            purpose = key.removeprefix('Reference fidelity: ')
            if state == 'not_applicable' and purpose in present_purposes:
                raise StudioError('reference_required', 'An applicable reference purpose cannot be waived with not_applicable.')
            if state == 'pass' and purpose in required_purposes and any(r['purpose'] == purpose for r in missing_references(project, shot, calibration_only=calibration_only)):
                raise StudioError('reference_required', 'Missing required references remain blocked; provide references or ask the creator to narrow scope.')
    normalized = normalize_review(review)['criteria']
    for key, value in normalized.items():
        if key.startswith('Reference fidelity: ') and value['state'] == 'not_applicable':
            purpose = key.removeprefix('Reference fidelity: ')
            value['reason'] = 'No applicable '+purpose+' reference in the saved scope.'
    return normalized


def technical_passed(project, shot, kind, *, calibration_only=False):
    from .production import criteria_for
    asset = next((a for a in project['assets'] if a['id'] == shot.get(kind+'_asset')), {})
    review = asset.get('review', {})
    inspected = {'image'} if kind == 'image' else {'beginning', 'middle', 'end'}
    return asset.get('execution_state') != 'needs_review' and bool(review) and not asset.get('stale') and not review.get('defect') and inspected <= set(review.get('inspected', [])) and not missing_references(project, shot, kind, calibration_only=calibration_only) and all(criterion_passed(project, shot, c, review.get('criteria', {}).get(c), kind, calibration_only=calibration_only) for c in criteria_for(project, shot, kind, calibration_only=calibration_only))


def criterion_passed(project, shot, criterion, value, kind='image', *, calibration_only=False):
    state = check_state(value)
    if state == 'pass':
        return True
    if state != 'not_applicable' or not criterion.startswith('Reference fidelity: '):
        return False
    purpose = criterion.removeprefix('Reference fidelity: ')
    return not any(r['purpose'] == purpose and (r['required'] or requirement_assets(project, shot, r)) for r in scoped_requirements(project, shot, kind, calibration_only=calibration_only))


def acceptance_current(project, asset, decision):
    return bool(asset and decision and not asset.get('stale') and decision.get('style_signature') == style_contract_signature(project)
                and decision.get('take_signature') == baseline_take_signature(project, asset))


def calibration_state(project):
    c = project.get('calibration')
    if not c:
        return {'mode': 'legacy', 'status': 'legacy'}
    shot = representative(project)
    state = {**copy.deepcopy(c), 'representative_shot_id': shot['id'] if shot else None}
    if c['mode'] == 'production':
        state['status'] = 'skipped'
        return state
    asset = next((a for a in project['assets'] if a['id'] == c.get('baseline_asset_id')), None)
    if c['status'] == 'approved' and acceptance_current(project, asset, c) and shot and shot.get('image_asset') == asset['id']:
        return state
    if pending_calibration_decision(project):
        state['status'] = 'pending_creator'
        return state
    state['status'] = 'rejected' if c['status'] == 'rejected' else 'not_started'
    if shot:
        candidate = next((a for a in project['assets'] if a['id'] == shot.get('image_asset')), None)
        if candidate and candidate_current(project, candidate) and technical_passed(project, shot, 'image', calibration_only=True):
            state['status'] = 'pending_creator'
    return state


def candidate_current(project, asset):
    c = project['calibration']
    rejected = {h.get('asset_id') for h in c['history'] if h['decision'] == 'reject'}
    return not asset.get('stale') and asset['id'] not in rejected and asset.get('calibration_style_signature') == style_contract_signature(project)


def style_override(project, shot):
    # Only explicit structural treatment overrides; ordinary scene/environment prose is not style inference.
    shared = effective_direction(project, {**shot, 'direction': {}})
    actual = effective_direction(project, shot)
    return any(actual[key] != shared[key] for key in ('art', 'lighting'))


def shot_style_accepted(project, shot):
    if not project.get('calibration') or project['calibration']['mode'] == 'production':
        return True
    if calibration_state(project)['status'] != 'approved':
        return False
    if shot['id'] == representative(project)['id'] or not style_override(project, shot):
        return True
    asset = next((a for a in project['assets'] if a['id'] == shot.get('image_asset')), None)
    return acceptance_current(project, asset, project['calibration']['shot_acceptances'].get(shot['id']))


def production_fidelity_action(project):
    c = project.get('calibration')
    if not c or (c['mode'] == 'calibration' and calibration_state(project)['status'] != 'approved'):
        return None
    for shot in project['shots']:
        missing = missing_references(project, shot, 'image')
        if missing:
            return {'action': 'ask_creator', 'step': 'visual_direction', 'shot_id': shot['id'], 'kind': 'image',
                    'reference_requirements': missing,
                    'message': 'Provide required '+', '.join(sorted({r['purpose'] for r in missing}))+' references or explicitly change the production obligation. Environment baseline acceptance does not approve identity/product fidelity.'}
        if shot.get('image_asset') and any(r['required'] for r in reference_requirements(project)) and not technical_passed(project, shot, 'image'):
            attention = shot.get('quality_retry_attention', {}).get('image')
            if attention or shot.get('quality_retry_exhausted', {}).get('image'):
                return {'action':'quality_attention', 'step':'visual_direction', 'shot_id':shot['id'], 'kind':'image',
                        'message':attention or 'Automatic quality retry limit reached. Inspect the defect and redesign or revise manually before spending again.'}
            from .production import criteria_for
            return {'action': 'record_quality', 'step': 'visual_direction', 'shot_id': shot['id'], 'kind': 'image',
                    'asset_id': shot['image_asset'], 'criteria': criteria_for(project, shot, 'image', calibration_only=False),
                    'message': 'Inspect the required production fidelity checks. The accepted baseline scope remains unchanged.'}
    return None


def pending_calibration_decision(project):
    c = project.get('calibration', {})
    if c.get('mode') != 'calibration':
        return None
    if c.get('pending_decision'):
        return c['pending_decision']
    # Compatibility with persisted pre-fix pending states. This restores only
    # an unresolved gate; historical inspectors/creator decisions are untouched.
    if c.get('status') == 'pending_creator':
        shot = representative(project)
        if shot and shot.get('image_asset'):
            return {'shot_id': shot['id'], 'asset_id': shot['image_asset'], 'source': 'persisted_pending_state'}
    return None


def remember_calibration_pending(project):
    c = project.get('calibration')
    if not c or c['mode'] != 'calibration' or c.get('pending_decision'):
        return
    pending = pending_calibration_decision(project)
    if not pending:
        action = calibration_action(project)
        if action and action['action'] == 'await_calibration_approval':
            pending = {'asset_id': action['asset_id'], 'shot_id': action['shot_id'],
                       'at': datetime.now(timezone.utc).isoformat(), 'source': 'technical_review_gate'}
    if pending:
        c['pending_decision'] = copy.deepcopy(pending)


def calibration_action(project):
    c = project.get('calibration')
    if not c or c['mode'] == 'production':
        return None
    pending = pending_calibration_decision(project)
    if pending:
        shot = next((s for s in project['shots'] if s['id'] == pending['shot_id']), None)
        asset = next((a for a in project['assets'] if a['id'] == pending['asset_id']), None)
        technical_ready = bool(shot and asset and shot.get('image_asset') == asset['id'] and candidate_current(project, asset) and technical_passed(project, shot, 'image', calibration_only=True))
        return {'action': 'await_calibration_approval', 'step': 'visual_direction', 'kind': 'image', **pending, 'technical_ready': technical_ready,
                'message': 'Waiting for the creator decision. Corrected technical evidence may be recorded; replacement generation requires creator rejection.'}
    state = calibration_state(project)
    shot = representative(project)
    if state['status'] == 'approved':
        shot = next((s for s in project['shots'] if s.get('image_asset') and not shot_style_accepted(project, s)), None)
        if not shot:
            return None
    if not shot:
        return {'action': 'ask_creator', 'step': 'visual_direction', 'message': 'Choose a current representative shot in the studio before calibration can continue.'}
    base = {'step': 'visual_direction', 'shot_id': shot['id'], 'kind': 'image'}
    missing = missing_references(project, shot, calibration_only=True)
    if missing:
        return {**base, 'action': 'ask_creator', 'reference_requirements': missing, 'message': 'Provide required '+', '.join(sorted({r['purpose'] for r in missing}))+' references, or explicitly narrow calibration scope in the studio.'}
    asset = next((a for a in project['assets'] if a['id'] == shot.get('image_asset')), None)
    if asset and candidate_current(project, asset):
        if not technical_passed(project, shot, 'image', calibration_only=True):
            from .production import criteria_for
            return {**base, 'action': 'record_quality', 'asset_id': asset['id'], 'criteria': criteria_for(project, shot, 'image', calibration_only=True), 'message': 'Inspect the actual calibration image and record technical evidence. Creator style acceptance is separate.'}
        return {**base, 'action': 'await_calibration_approval', 'asset_id': asset['id'], 'technical_ready': True, 'message': 'Technical inspection passed. Waiting for creator style acceptance in the studio.'}
    if not shot['image_prompt'].strip():
        return {**base, 'action': 'write_prompt', 'message': 'Prepare the representative image prompt.'}
    checks = preflight(project, shot['id'], 'image')
    if checks['errors']:
        return {**base, 'action': 'resolve_preflight', 'preflight': checks, 'message': 'Resolve blocking production checks before calibration.'}
    return {**base, 'action': 'generate', 'message': 'Generate only the representative calibration image.'}


class Calibration:
    def _guard_calibration_pending(self, p, actor, shot_id=None):
        if actor == 'user':
            return
        action = calibration_action(p)
        if action and action['action'] == 'await_calibration_approval' and (shot_id is None or action.get('shot_id') == shot_id):
            raise StudioError('calibration_pending', 'Wait for the creator to accept or reject the inspected take before replacing its inputs or requesting another image.', 409)

    def _guard_calibration_mutation(self, before, after, actor):
        if actor == 'user':
            return
        action = calibration_action(before)
        if not action or action['action'] != 'await_calibration_approval':
            return
        asset = next(a for a in before['assets'] if a['id'] == action['asset_id'])
        target = next((s for s in after['shots'] if s['id'] == action['shot_id']), None)
        if not target or target.get('image_asset') != asset['id'] or baseline_take_signature(before, asset) != baseline_take_signature(after, asset):
            self._guard_calibration_pending(before, actor)

    def set_calibration_mode(self, project_id, mode, expected_revision, actor):
        from .agent_rules import validate_revision
        if actor != 'user':
            raise StudioError('human_only', 'Only the creator can adopt or skip calibration.', 403)
        validate_revision(expected_revision)
        if mode not in {'calibration', 'production'}:
            raise StudioError('invalid_calibration', 'Choose calibration or production mode.')
        def update(p):
            c = p.setdefault('calibration', default_calibration())
            c.update(mode=mode, status='not_started', baseline_asset_id=None, pending_decision=None)
            c['history'].append({'decision': 'skip' if mode == 'production' else 'adopt', 'actor': actor, 'at': datetime.now(timezone.utc).isoformat(), 'scope': copy.deepcopy(c['scope'])})
            self._reopen(p, 'visual_direction'); self._progress(p)
        return self.mutate(project_id, expected_revision, update)

    def configure_calibration(self, project_id, representative_shot_id, scope, expected_revision, actor):
        from .agent_rules import validate_revision
        if actor != 'user':
            raise StudioError('human_only', 'Only the creator can choose or narrow calibration scope.', 403)
        validate_revision(expected_revision)
        if not isinstance(scope, list) or not scope or any(v not in PURPOSES for v in scope) or len(set(scope)) != len(scope):
            raise StudioError('invalid_calibration', 'Choose distinct style, identity, product or layout purposes.')
        def update(p):
            if not any(s['id'] == representative_shot_id for s in p['shots']):
                raise StudioError('invalid_calibration', 'Choose a current representative shot.')
            if any(j['status'] in {'running', 'awaiting_external_output', 'queued'} for j in p['jobs']):
                raise StudioError('job_running', 'Close pending generation before changing calibration scope.', 409)
            c = p.setdefault('calibration', default_calibration())
            c.update(representative_shot_id=representative_shot_id, representative_selection_source='human_ui', scope=list(scope), status='not_started', baseline_asset_id=None, pending_decision=None)
            c['history'].append({'decision': 'scope', 'actor': actor, 'at': datetime.now(timezone.utc).isoformat(), 'scope': list(scope), 'representative_shot_id': representative_shot_id})
            self._reopen(p, 'visual_direction'); self._progress(p)
        return self.mutate(project_id, expected_revision, update)

    def review_calibration(self, project_id, asset_id, approve, note, expected_revision, actor):
        from .agent_rules import validate_revision
        if actor != 'user':
            raise StudioError('human_only', 'Creator style acceptance cannot be asserted by an agent.', 403)
        validate_revision(expected_revision)
        if type(approve) is not bool or not isinstance(note, str) or len(note) > 8000 or (not approve and not note.strip()):
            raise StudioError('invalid_calibration', 'Use an approval boolean and feedback for a rejection.')
        def update(p):
            action = calibration_action(p)
            if not action or action.get('action') != 'await_calibration_approval' or action.get('asset_id') != asset_id:
                raise StudioError('calibration_blocked', 'Inspect the current non-stale take before creator style acceptance.', 409)
            if approve and not action.get('technical_ready', False):
                raise StudioError('calibration_blocked', 'Correct the current technical evidence before creator acceptance, or reject the take to authorize repair.', 409)
            asset = next(a for a in p['assets'] if a['id'] == asset_id)
            shot = next(s for s in p['shots'] if s['id'] == asset['shot_id'])
            c = p['calibration']; is_baseline = shot['id'] == representative(p)['id']
            decision = {'decision': 'approve' if approve else 'reject', 'asset_id': asset_id, 'shot_id': shot['id'],
                        'actor': actor, 'at': datetime.now(timezone.utc).isoformat(), 'note': note.strip(), 'scope': copy.deepcopy(c['scope']),
                        'style_signature': style_contract_signature(p), 'take_signature': baseline_take_signature(p, asset)}
            c['history'].append(decision)
            c['pending_decision'] = None
            if approve:
                if is_baseline:
                    c.update(status='approved', baseline_asset_id=asset_id, representative_shot_id=shot['id'], style_signature=decision['style_signature'], take_signature=decision['take_signature'])
                else:
                    c['shot_acceptances'][shot['id']] = decision
            else:
                if is_baseline:
                    c.update(status='rejected', feedback=note.strip())
                shot['direction']['quality']['revision_reason'] = note.strip()
                self._invalidate_selected(p, {shot['id']: {'image'}})
            self._progress(p)
        return self.mutate(project_id, expected_revision, update)
