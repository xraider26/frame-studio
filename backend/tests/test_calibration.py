from workflow_fixtures import return_fixture
import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from studio.workflow import Studio
from studio.store import StudioError, load
from studio.production import criteria_for, quality_passed
from studio.api import create_app
from test_generation_setup import selection


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = Studio(self.root/'db', self.root/'media', self.root/'inbox')

    def prepare(self):
        p = self.s.create_project('Calibration', 'custom', generation_setup={'version': 1, 'image': selection(), 'video': selection('video')})
        p = self.s.update_settings(p['id'], {'creative_intake': {'vision': 'Amber worlds', 'art_style': 'Painterly amber', 'purpose': 'Film'}}, p['revision'], 'user')
        for step in ['brief', 'script']:
            p = self.s.complete_step(p['id'], step, {'text': step}, p['revision'], 'user')
        p = self.s.update_shots(p['id'], [{'title': 'Garden', 'image_prompt': 'Amber flowers', 'motion_prompt': 'Still'}, {'title': 'Ocean', 'image_prompt': 'Amber ocean', 'motion_prompt': 'Waves'}], p['revision'], 'user')
        return p

    def take(self, p, request='first'):
        task = self.s.claim_next(p['id'], 'agent:test', request)
        self.assertIsNotNone(task.get('job'), task)
        file = self.s.inbox/(request+'.png'); Image.new('RGB', (32, 18), 'orange').save(file)
        result = return_fixture(self.s, task['job']['id'], str(file), 'agent:test')
        return self.s.get(p['id']), result['asset']

    def inspect(self, p, a):
        shot = next(s for s in p['shots'] if s['id'] == a['shot_id'])
        return self.s.record_take_review(p['id'], a['id'], {'criteria': {c: True for c in criteria_for(p, shot, 'image')}, 'inspected': ['image'], 'notes': 'Inspected actual fixture'}, p['revision'], 'agent:test')

    def approved(self):
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        self.assertTrue(hasattr(self.s, 'review_calibration'), 'Missing creator baseline decision')
        return self.s.review_calibration(p['id'], a['id'], True, 'Accept amber treatment', p['revision'], 'user'), a

    def test_one_image_then_technical_inspection_then_creator_gate(self):
        p, a = self.take(self.prepare())
        self.assertEqual(self.s.next_action(p['id'])['action'], 'record_quality')
        p = self.inspect(p, a)
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'await_calibration_approval')
        self.assertIsNone(self.s.claim_next(p['id'], 'agent:other', 'second')['job'])
        self.assertEqual(p['assets'][0]['review']['actor'], 'agent:test')
        self.assertEqual(self.s.production_queue()['items'][0]['state'], 'awaiting_approval')
        self.assertEqual(self.s.claim_queue_task('agent:other', 'queue')['status'], 'idle')

    def test_technical_pass_does_not_approve_and_requires_actual_inspection_even_policy_off(self):
        p = self.prepare()
        p = self.s.update_production(p['id'], {'require_recorded_checks': False}, p['revision'], 'user')
        p, a = self.take(p)
        self.assertEqual(self.s.next_action(p['id'])['action'], 'record_quality')
        self.assertTrue(hasattr(self.s, 'review_calibration'), 'Missing creator review')
        with self.assertRaises(StudioError): self.s.review_calibration(p['id'], a['id'], True, '', p['revision'], 'user')
        p = self.inspect(p, a)
        self.assertNotEqual(p['calibration']['status'], 'approved')

    def test_acceptance_releases_second_world_and_video_only_change_preserves_it(self):
        p, a = self.approved()
        self.assertEqual(self.s.next_action(p['id'])['shot_id'], p['shots'][1]['id'])
        video = selection('video'); video['tool_name'] = 'New future destination'
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'video': video}, p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['shot_id'], p['shots'][1]['id'])
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')

    def test_new_world_prompt_does_not_revoke_shared_baseline(self):
        p, a = self.approved()
        shots = copy.deepcopy(p['shots']); shots[1]['image_prompt'] = 'A distant amber desert'
        shots.append({'title': 'Mountains', 'image_prompt': 'Amber peaks', 'motion_prompt': 'Clouds'})
        p = self.s.update_shots(p['id'], shots, p['revision'], 'agent:test')
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
        self.assertEqual(self.s.next_action(p['id'])['shot_id'], p['shots'][1]['id'])

    def test_shared_style_image_tool_reference_and_baseline_prompt_revoke(self):
        for change in ['style', 'tool', 'prompt', 'reference']:
            with self.subTest(change=change):
                p, a = self.approved()
                if change == 'style': p = self.s.update_production(p['id'], {'defaults': {'art': {'palette': 'Blue'}}}, p['revision'], 'user')
                if change == 'tool':
                    image = selection(); image['tool_name'] = 'Other image app'
                    p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': image}, p['revision'], 'user')
                if change == 'prompt':
                    shots = copy.deepcopy(p['shots']); shots[0]['image_prompt'] = 'A different representative'
                    p = self.s.update_shots(p['id'], shots, p['revision'], 'user')
                if change == 'reference':
                    file = self.s.inbox/'ref.png'; Image.new('RGB', (16, 16), 'blue').save(file)
                    p = self.s.import_reference(p['id'], str(file), 'New style', p['revision'], 'user')
                self.assertNotEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
                self.assertEqual(self.s.next_action(p['id']).get('shot_id'), p['shots'][0]['id'])

    def test_rejection_preserves_take_and_feedback_and_only_repairs_representative(self):
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        self.assertTrue(hasattr(self.s, 'review_calibration'), 'Missing rejection')
        p = self.s.review_calibration(p['id'], a['id'], False, 'More translucent petals', p['revision'], 'user')
        self.assertTrue(Path(a['path']).is_file())
        old = next(x for x in p['assets'] if x['id'] == a['id'])
        self.assertEqual(old['review']['actor'], 'agent:test')
        self.assertIn('More translucent petals', p['shots'][0]['direction']['quality']['revision_reason'])
        with self.assertRaises(StudioError): self.s.select_take(p['id'], a['id'], p['revision'], 'agent:test')
        p, replacement = self.take(p, 'repair')
        self.assertEqual(replacement['shot_id'], a['shot_id'])
        self.assertEqual(len(p['assets']), 2)
        self.assertEqual(self.s.next_action(p['id'])['action'], 'record_quality')

    def test_agents_cannot_approve_skip_or_narrow_reference_requirements(self):
        p = self.prepare()
        for method in ['review_calibration', 'set_calibration_mode']:
            self.assertTrue(hasattr(self.s, method), 'Missing '+method)
        with self.assertRaises(StudioError) as e: self.s.set_calibration_mode(p['id'], 'production', p['revision'], 'agent:test')
        self.assertEqual(e.exception.status, 403)
        with self.assertRaises(StudioError) as e: self.s.review_calibration(p['id'], 'fake', True, '', p['revision'], 'agent:test')
        self.assertEqual(e.exception.status, 403)
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': True, 'source_rule': 'creator:recognizable'}]}, p['revision'], 'user')
        for requirements in [[], [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': False, 'source_rule': 'creator:recognizable'}]]:
            with self.assertRaises(StudioError) as e: self.s.update_production(p['id'], {'reference_requirements': requirements}, p['revision'], 'agent:test')
            self.assertEqual(e.exception.status, 403)

    def test_required_identity_missing_blocks_and_not_applicable_cannot_waive_it(self):
        p = self.prepare()
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': True, 'source_rule': 'creator:recognizable'}]}, p['revision'], 'user')
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'ask_creator')
        self.assertIn('identity', action['message'])
        self.assertIsNone(self.s.claim_next(p['id'], 'agent:test', 'blocked')['job'])

    def test_environment_scope_and_style_reference_can_calibrate_without_face_claim(self):
        p = self.prepare()
        file = self.s.inbox/'style.png'; Image.new('RGB', (32, 18), 'orange').save(file)
        p = self.s.import_reference(p['id'], str(file), 'Amber style', p['revision'], 'user')
        style = p['assets'][-1]['id']
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': '', 'kind': 'environment', 'purpose': 'style', 'required': True, 'asset_ids': [style], 'source_rule': 'creator:amber'}]}, p['revision'], 'user')
        self.assertTrue(hasattr(self.s, 'configure_calibration'), 'Missing creator scope control')
        p = self.s.configure_calibration(p['id'], p['shots'][0]['id'], ['style', 'layout'], p['revision'], 'user')
        p, a = self.take(p)
        criteria = criteria_for(p, p['shots'][0], 'image')
        self.assertIn('Reference fidelity: style', criteria)
        self.assertNotIn('Reference fidelity: identity', criteria)
        checks = {c: {'state': 'pass'} for c in criteria}
        checks['Reference fidelity: identity'] = {'state': 'not_applicable', 'reason': 'Outside creator-approved environment scope'}
        p = self.s.record_take_review(p['id'], a['id'], {'version': 2, 'criteria': checks, 'inspected': ['image']}, p['revision'], 'agent:test')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')
        p = self.s.review_calibration(p['id'], a['id'], True, 'Environment treatment only', p['revision'], 'user')
        self.assertEqual(p['calibration']['history'][-1]['scope'], ['style', 'layout'])

    def test_versioned_review_reason_validation_required_reference_and_boolean_normalization(self):
        p, a = self.take(self.prepare())
        for state in ['not_applicable', 'blocked']:
            with self.assertRaises(StudioError): self.s.record_take_review(p['id'], a['id'], {'version': 2, 'criteria': {'Optional': {'state': state}}, 'inspected': ['image']}, p['revision'], 'agent:test')
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': True, 'source_rule': 'creator:hero'}]}, p['revision'], 'user')
        with self.assertRaises(StudioError): self.s.record_take_review(p['id'], a['id'], {'version': 2, 'criteria': {'Reference fidelity: identity': {'state': 'not_applicable', 'reason': 'No portrait'}}, 'inspected': ['image']}, p['revision'], 'agent:test')
        old = {'criteria': {'Old': True}, 'actor': 'agent:historical', 'at': '2020', 'inspected': ['image']}
        import json
        p['assets'][0]['review'] = old
        normalized = load(json.dumps(p))['assets'][0]['review']
        self.assertEqual(normalized['criteria']['Old'], {'state': 'pass', 'reason': ''})
        self.assertEqual(normalized['actor'], 'agent:historical')
        self.assertEqual(normalized['at'], '2020')
        self.assertNotEqual(p['calibration']['status'], 'approved')

    def test_structural_shot_style_override_requires_its_own_creator_acceptance(self):
        p, a = self.approved()
        shots = copy.deepcopy(p['shots']); shots[1]['direction']['art']['palette'] = 'Ultramarine'
        p = self.s.update_shots(p['id'], shots, p['revision'], 'agent:test')
        p, other = self.take(p, 'override'); p = self.inspect(p, other)
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'await_calibration_approval')
        self.assertEqual(action['asset_id'], other['id'])
        p = self.s.review_calibration(p['id'], other['id'], True, 'Accept this override', p['revision'], 'user')
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
        self.assertEqual(p['calibration']['baseline_asset_id'], a['id'])

    def test_stale_approval_and_two_workers_only_one_representative(self):
        p = self.prepare()
        contract_before = self.s.get_workflow_contract(p['id'])['contract_version']
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = list(pool.map(lambda n: self.s.claim_next(p['id'], 'agent:'+str(n), 'race-'+str(n)), range(2)))
        self.assertEqual(self.s.get_workflow_contract(p['id'])['contract_version'], contract_before, 'Automatically pinning the current representative does not change policy')
        self.assertEqual(tasks[0]['job']['id'], tasks[1]['job']['id'])
        self.assertEqual(len(self.s.get(p['id'])['jobs']), 1)
        file = self.s.inbox/'race.png'; Image.new('RGB', (32, 18)).save(file)
        a = return_fixture(self.s, tasks[0]['job']['id'], str(file), 'agent:0')['asset']
        p = self.inspect(self.s.get(p['id']), a)
        self.assertTrue(hasattr(self.s, 'review_calibration'), 'Missing stale decision guard')
        with self.assertRaises(StudioError) as e: self.s.review_calibration(p['id'], a['id'], True, '', p['revision']-1, 'user')
        self.assertEqual(e.exception.code, 'revision_conflict')

    def test_explicit_human_skip_and_legacy_opt_in_do_not_inherit_approval(self):
        p = self.prepare()
        self.assertTrue(hasattr(self.s, 'set_calibration_mode'), 'Missing human skip/opt-in')
        p = self.s.set_calibration_mode(p['id'], 'production', p['revision'], 'user')
        self.assertEqual(p['calibration']['history'][-1]['decision'], 'skip')
        legacy = self.s.create_project('Legacy fixture', 'custom')
        self.assertNotIn('calibration', legacy)
        adopted = self.s.set_calibration_mode(legacy['id'], 'calibration', legacy['revision'], 'user')
        self.assertEqual(adopted['calibration']['status'], 'not_started')
        self.assertIsNone(adopted['calibration']['baseline_asset_id'])

    def test_http_agent_tokens_cannot_forge_human_controls_and_public_defaults_apply(self):
        app = create_app(self.root/'api', 'agent', 'human'); client = TestClient(app)
        def call(token, op, **args): return client.post('/studio/v1/command', headers={'Authorization': 'Bearer '+token}, json={'operation': op, 'arguments': args, 'actor': 'user'})
        p = call('agent', 'create_project', name='Public').json()
        self.assertEqual(p.get('calibration', {}).get('mode'), 'calibration')
        for op, args in [('review_calibration', {'asset_id': 'fake', 'approve': True, 'note': ''}), ('set_calibration_mode', {'mode': 'production'}), ('configure_calibration', {'representative_shot_id': p['shots'][0]['id'], 'scope': ['style']})]:
            response = call('agent', op, project_id=p['id'], expected_revision=p['revision'], **args)
            self.assertEqual(response.status_code, 403, response.text)
        response = call('human', 'set_calibration_mode', project_id=p['id'], mode='production', expected_revision=p['revision'])
        self.assertEqual(response.status_code, 200, response.text)
        clone = call('agent', 'duplicate_project', project_id=p['id'], expected_revision=response.json()['revision'])
        # Agent needs the workflow acknowledgement before duplication; human duplication still resets acceptance.
        clone = call('human', 'duplicate_project', project_id=p['id']).json()
        self.assertEqual(clone['calibration']['mode'], 'calibration')
        batch = call('agent', 'create_batch', name='Batch', idea='Worlds', count=2, request_id='batch').json()
        for key in batch['project_ids']:
            value = call('agent', 'get_project', project_id=key).json()
            self.assertEqual(value['calibration']['mode'], 'calibration')

    def test_provider_submission_cannot_bypass_calibration_via_old_job(self):
        from studio.providers import Providers
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        def old_job(value):
            job = copy.deepcopy(value['jobs'][0]); job.update(id='forged-old', shot_id=value['shots'][1]['id'], status='awaiting_external_output')
            value['jobs'].append(job)
        p = self.s.mutate(p['id'], p['revision'], old_job)
        providers = Providers(self.s, self.root/'connections.json')
        providers.connections['fixture'] = {'id': 'fixture', 'name': 'Fixture', 'enabled': True, 'max_requests': 10, 'used_requests': 0, 'adapter': 'json_job_api'}
        with patch('studio.providers.asyncio.create_task') as submit:
            with self.assertRaises(StudioError): providers.submit('forged-old', 'fixture')
            submit.assert_not_called()
        self.assertEqual(providers.connections['fixture']['used_requests'], 0)

    def test_step_policy_template_and_mutable_fields_cannot_forge_creator_acceptance(self):
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        p = self.s.set_policy(p['id'], {'visual_direction': False}, p['revision'])
        self.assertEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')
        with self.assertRaises(StudioError):
            self.s.update_production(p['id'], {'calibration': {'mode': 'production', 'status': 'approved'}}, p['revision'], 'agent:test')
        shots = copy.deepcopy(p['shots']); shots[1]['image_asset'] = a['id']; shots[1]['calibration_approved'] = True
        p = self.s.update_shots(p['id'], shots, p['revision'], 'agent:test')
        self.assertIsNone(p['shots'][1]['image_asset'])
        saved = self.s.save_project_template(p['id'], 'Skip attempt', '', ['workflow'], p['revision'])
        p = self.s.apply_project_template(p['id'], saved['id'], ['workflow'], p['revision'], saved['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')

    def test_custom_reference_checks_are_not_removed_by_scope_normalization(self):
        p = self.prepare()
        p = self.s.update_production(p['id'], {'defaults': {'quality': {'criteria': ['Compare crop with reference edge']}}}, p['revision'], 'user')
        p, a = self.take(p)
        criteria = criteria_for(p, p['shots'][0], 'image')
        self.assertIn('Compare crop with reference edge', criteria)
        checks = {c: True for c in criteria if c != 'Compare crop with reference edge'}
        p = self.s.record_take_review(p['id'], a['id'], {'criteria': checks, 'inspected': ['image']}, p['revision'], 'agent:test')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'record_quality')

    def test_new_requirement_after_environment_baseline_cannot_borrow_identity_approval(self):
        p = self.prepare()
        p = self.s.configure_calibration(p['id'], p['shots'][0]['id'], ['style', 'layout'], p['revision'], 'user')
        p, a = self.take(p); p = self.inspect(p, a)
        p = self.s.review_calibration(p['id'], a['id'], True, 'Environment only', p['revision'], 'user')
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': True, 'source_rule': 'creator:hero'}]}, p['revision'], 'user')
        p, a = self.take(p, 'environment-again'); p = self.inspect(p, a)
        p = self.s.review_calibration(p['id'], a['id'], True, 'Environment only', p['revision'], 'user')
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'ask_creator')
        self.assertIn('identity', action['message'])

    def test_optional_irrelevant_reference_can_be_not_applicable_with_server_reason(self):
        p = self.prepare()
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': '', 'kind': 'style', 'purpose': 'style', 'required': False, 'source_rule': 'optional'}]}, p['revision'], 'user')
        p, a = self.take(p)
        checks = {c: {'state': 'pass'} for c in criteria_for(p, p['shots'][0], 'image')}
        checks['Reference fidelity: style'] = {'state': 'not_applicable', 'reason': 'My unsupported assertion'}
        p = self.s.record_take_review(p['id'], a['id'], {'version': 2, 'criteria': checks, 'inspected': ['image']}, p['revision'], 'agent:test')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')
        self.assertEqual(p['assets'][0]['review']['criteria']['Reference fidelity: style']['reason'], 'No applicable style reference in the saved scope.')

    def test_comfy_and_json_scheduled_execution_recheck_the_shared_gate_before_network(self):
        import asyncio
        from studio.providers import Providers
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        def old_job(value):
            job = copy.deepcopy(value['jobs'][0]); job.update(id='scheduled', shot_id=value['shots'][1]['id'], status='running')
            value['jobs'].append(job)
        self.s.mutate(p['id'], p['revision'], old_job)
        providers = Providers(self.s, self.root/'connections.json')
        conn = {'id': 'fixture', 'name': 'Fixture', 'base_url': 'http://localhost:8188', 'enabled': True, 'api_key': '', 'comfy': {}}
        providers.connections['fixture'] = {**conn, 'adapter': 'comfyui'}
        with patch('studio.providers.httpx.AsyncClient', side_effect=AssertionError('Network must remain untouched')):
            with self.assertRaises(StudioError): asyncio.run(providers._run_comfy('scheduled', conn))
            asyncio.run(providers._run('scheduled', {**conn, 'adapter': 'json_job_api'}))
        _, job = self.s.find_job('scheduled')
        self.assertEqual(job['status'], 'failed')
        self.assertNotIn('remote_prompt_id', job)

    def test_reordering_or_removing_representative_does_not_authorize_another_image(self):
        p, a = self.take(self.prepare())
        p = self.inspect(p, a)
        shots = list(reversed(copy.deepcopy(p['shots'])))
        p = self.s.update_shots(p['id'], shots, p['revision'], 'agent:test')
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'await_calibration_approval')
        self.assertEqual(action['shot_id'], a['shot_id'])
        with self.assertRaises(StudioError):
            self.s.update_shots(p['id'], [p['shots'][0]], p['revision'], 'agent:test')

    def test_agent_mutations_cannot_spend_again_while_creator_decision_pending(self):
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        shots = copy.deepcopy(p['shots']); shots[0]['image_prompt'] = 'Another attempt without creator feedback'
        operations = [lambda: self.s.update_shots(p['id'], shots, p['revision'], 'agent:test'),
                      lambda: self.s.update_production(p['id'], {'defaults': {'art': {'palette': 'Blue'}}}, p['revision'], 'agent:test'),
                      lambda: self.s.update_settings(p['id'], {'palette': 'Blue'}, p['revision'], 'agent:test'),
                      lambda: self.s.revise_shot(p['id'], a['shot_id'], 'image', 'Generate again', p['revision'], 'agent:test')]
        for operation in operations:
            with self.assertRaises(StudioError) as error: operation()
            self.assertEqual(error.exception.code, 'calibration_pending')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')

    def test_calibration_preserves_optional_production_inspection_policy(self):
        p = self.prepare()
        p = self.s.update_production(p['id'], {'require_recorded_checks': False}, p['revision'], 'user')
        p, a = self.take(p); p = self.inspect(p, a)
        p = self.s.review_calibration(p['id'], a['id'], True, 'Baseline accepted', p['revision'], 'user')
        p, other = self.take(p, 'production-policy')
        self.assertEqual(self.s.next_action(p['id'])['kind'], 'video')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'generate')

    def test_creator_skip_does_not_waive_missing_required_identity(self):
        p = self.prepare()
        for _ in range(2):
            p, a = self.take(p, 'fixture-'+str(_)); p = self.inspect(p, a)
            if _ == 0: p = self.s.review_calibration(p['id'], a['id'], True, 'Accepted', p['revision'], 'user')
        p = self.s.set_calibration_mode(p['id'], 'production', p['revision'], 'user')
        p = self.s.update_production(p['id'], {'require_recorded_checks': False, 'reference_requirements': [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': True, 'source_rule': 'creator:hero'}]}, p['revision'], 'user')
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'ask_creator')
        self.assertIn('identity', action['message'])

    def test_duplicate_remaps_reference_requirements_and_saved_template_keeps_requiredness(self):
        p = self.prepare()
        file = self.s.inbox/'style.png'; Image.new('RGB', (16, 16), 'orange').save(file)
        p = self.s.import_reference(p['id'], str(file), 'Style reference', p['revision'], 'user')
        reference_id = p['assets'][-1]['id']
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': '', 'kind': 'style', 'purpose': 'style', 'required': True, 'asset_ids': [reference_id], 'source_rule': 'creator:style'}]}, p['revision'], 'user')
        clone = self.s.duplicate_project(p['id'], 'Clone', 'user', adopt_generation_setup=True)
        clone = self.s.set_generation_setup(clone['id'], {'version': 1, 'image': selection(), 'video': selection('video')}, clone['revision'], 'user')
        self.assertNotEqual(clone['production']['reference_requirements'][0]['asset_ids'], [reference_id])
        self.assertEqual(self.s.next_action(clone['id'])['action'], 'generate')
        saved = self.s.save_project_template(p['id'], 'Fidelity template', '', ['story'], p['revision'])
        fresh = self.s.create_project('From template', saved['id'], generation_setup={'version': 1, 'image': selection(), 'video': selection('video')})
        self.assertTrue(fresh['production']['reference_requirements'][0]['required'])
        self.assertEqual(fresh['production']['reference_requirements'][0]['asset_ids'], [])
        self.assertEqual(fresh['calibration']['mode'], 'calibration')

    def test_pending_creator_decision_survives_technical_evidence_reset_and_rejection(self):
        for review in [{'criteria': {}, 'inspected': []}, {'criteria': {'Identity and composition serve the shot': False}, 'inspected': ['image'], 'defect': 'Corrected evidence'}]:
            with self.subTest(review=review):
                p, a = self.take(self.prepare()); p = self.inspect(p, a)
                self.assertEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')
                p = self.s.record_take_review(p['id'], a['id'], review, p['revision'], 'agent:test')
                self.assertEqual(p['assets'][0]['review']['inspected'], review['inspected'])
                with self.assertRaises(StudioError) as error:
                    self.s.revise_shot(p['id'], a['shot_id'], 'image', 'Try again without human decision', p['revision'], 'agent:test')
                self.assertEqual(error.exception.code, 'calibration_pending')
                self.assertIsNone(self.s.claim_next(p['id'], 'agent:test', 'after-reset')['job'])
                self.assertEqual(len(self.s.get(p['id'])['jobs']), 1)
                with self.assertRaises(StudioError) as error: self.s.review_calibration(p['id'], a['id'], True, 'Cannot accept invalid evidence', self.s.get(p['id'])['revision'], 'user')
                self.assertEqual(error.exception.code, 'calibration_blocked')
                p = self.s.review_calibration(p['id'], a['id'], False, 'Creator requests repair', self.s.get(p['id'])['revision'], 'user')
                p, repair = self.take(p, 'authorized-repair')
                self.assertEqual(repair['shot_id'], a['shot_id'])

    def test_pending_creator_decision_survives_batch_automatic_retry_and_provider_start(self):
        from studio.providers import Providers
        p = self.prepare()
        batch = self.s.create_batch('Retry authority', 'Amber', 'variations', 'custom', 1, 'retry-authority', 'user', policy={'auto_retry': True})
        p = self.s.mutate(p['id'], p['revision'], lambda v: v.update(batch_id=batch['id']))
        p, a = self.take(p); p = self.inspect(p, a)
        p = self.s.record_take_review(p['id'], a['id'], {'criteria': {'Identity and composition serve the shot': False}, 'inspected': ['image'], 'defect': 'Newly noticed flaw'}, p['revision'], 'agent:test')
        self.assertEqual(p['shots'][0]['image_asset'], a['id'], 'Evidence correction must not automatically replace a take awaiting the creator')
        self.assertEqual(p['shots'][0].get('quality_retries', {}).get('image', 0), 0)
        self.assertIsNone(self.s.claim_next(p['id'], 'agent:test', 'no-auto-retry')['job'])
        def scheduled(value):
            old = copy.deepcopy(value['jobs'][0]); old.update(id='old-provider', status='awaiting_external_output')
            value['jobs'].append(old)
        p = self.s.get(p['id'])
        self.s.mutate(p['id'], p['revision'], scheduled)
        providers = Providers(self.s, self.root/'retry-connections')
        providers.connections['fixture'] = {'enabled': True, 'used_requests': 0, 'max_requests': 5, 'adapter': 'json_job_api'}
        with self.assertRaises(StudioError): providers.submit('old-provider', 'fixture')
        self.assertEqual(providers.connections['fixture']['used_requests'], 0)

    def test_corrected_evidence_can_restore_acceptance_without_a_new_image(self):
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        p = self.s.record_take_review(p['id'], a['id'], {'criteria': {}, 'inspected': []}, p['revision'], 'agent:test')
        p = self.inspect(p, a)
        p = self.s.review_calibration(p['id'], a['id'], True, 'Accept after evidence correction', p['revision'], 'user')
        self.assertEqual(p['calibration']['baseline_asset_id'], a['id'])
        self.assertEqual(len(p['jobs']), 1)

    def environment_image(self, with_identity_reference=False):
        p = self.s.create_project('One environment baseline', 'custom', output_type='image', generation_setup={'version': 1, 'image': selection()})
        p = self.s.update_settings(p['id'], {'creative_intake': {'vision': 'Amber landscape', 'art_style': 'Amber painterly', 'purpose': 'One image'}}, p['revision'], 'user')
        for step in ['brief', 'script']:
            p = self.s.complete_step(p['id'], step, {'text': step}, p['revision'], 'user')
        p = self.s.update_shots(p['id'], [{'title': 'Landscape', 'image_prompt': 'Amber garden'}], p['revision'], 'user')
        asset_ids = []
        if with_identity_reference:
            file = self.s.inbox/'canonical.png'; Image.new('RGB', (16, 16), 'orange').save(file)
            p = self.s.import_reference(p['id'], str(file), 'Canonical identity', p['revision'], 'user')
            asset_ids = [p['assets'][-1]['id']]
        p = self.s.update_production(p['id'], {'reference_requirements': [{'entity_id': 'hero', 'kind': 'character', 'purpose': 'identity', 'required': True, 'asset_ids': asset_ids, 'source_rule': 'creator:hero'}]}, p['revision'], 'user')
        p = self.s.configure_calibration(p['id'], p['shots'][0]['id'], ['style', 'layout'], p['revision'], 'user')
        p, a = self.take(p); p = self.inspect(p, a)
        p = self.s.review_calibration(p['id'], a['id'], True, 'Environment style only', p['revision'], 'user')
        return p, a

    def test_environment_baseline_does_not_promote_representative_to_final_image(self):
        p, a = self.environment_image()
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
        self.assertEqual(p['calibration']['history'][-1]['scope'], ['style', 'layout'])
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'ask_creator')
        self.assertIn('identity', action['message'])
        self.assertFalse(p['steps']['visual_direction']['ready'])
        self.assertNotIn(p['steps']['visual_direction']['status'], ['approved', 'auto_proceeded'])
        self.assertFalse(quality_passed(p, p['shots'][0], 'image'))
        with self.assertRaises(StudioError): self.s.complete_step(p['id'], 'final_review', {'text': 'Premature final'}, p['revision'], 'agent:test')

    def test_skipped_and_readopted_scope_still_requires_full_production_fidelity(self):
        p, a = self.environment_image()
        p = self.s.set_calibration_mode(p['id'], 'production', p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'ask_creator')
        self.assertFalse(p['steps']['visual_direction']['ready'])
        p = self.s.set_calibration_mode(p['id'], 'calibration', p['revision'], 'user')
        p = self.s.review_calibration(p['id'], a['id'], True, 'Readopt environment scope only', p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'ask_creator')
        self.assertFalse(p['steps']['visual_direction']['ready'])
        # Only an explicit human change to the actual production obligation can clear it.
        p = self.s.update_production(p['id'], {'reference_requirements': []}, p['revision'], 'user')
        p, replacement = self.take(p, 'narrowed-production'); p = self.inspect(p, replacement)
        p = self.s.review_calibration(p['id'], replacement['id'], True, 'Accept changed production obligation', p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['step'], 'final_review')

    def test_persisted_pending_metadata_keeps_human_authority_after_evidence_correction(self):
        p, a = self.take(self.prepare()); p = self.inspect(p, a)
        def pre_fix_metadata(v):
            v['calibration'].pop('pending_decision', None)
        p = self.s.mutate(p['id'], p['revision'], pre_fix_metadata)
        history = copy.deepcopy(p['calibration']['history'])
        p = self.s.record_take_review(p['id'], a['id'], {'criteria': {}, 'inspected': []}, p['revision'], 'agent:correction')
        self.assertEqual(p['calibration']['history'], history)
        self.assertEqual(p['assets'][0]['review']['actor'], 'agent:correction')
        self.assertEqual(p['assets'][0]['review_history'][0]['actor'], 'agent:test')
        with self.assertRaises(StudioError): self.s.revise_shot(p['id'], a['shot_id'], 'image', 'Bypass old metadata', p['revision'], 'agent:test')
        self.assertIsNone(self.s.claim_next(p['id'], 'agent:test', 'persisted-bypass')['job'])

    def test_persisted_ready_state_cannot_bypass_full_production_requirements(self):
        p, a = self.environment_image()
        def old_readiness(v):
            v['steps']['visual_direction'] = {'ready': True, 'status': 'auto_proceeded'}
        p = self.s.mutate(p['id'], p['revision'], old_readiness)
        history = copy.deepcopy(p['calibration']['history'])
        self.assertEqual(self.s.next_action(p['id'])['action'], 'ask_creator')
        current = self.s.get_project(p['id'])
        self.assertFalse(current['steps']['visual_direction']['ready'])
        self.assertEqual(current['calibration']['history'], history)
        self.assertEqual(current['calibration_state']['status'], 'approved')

    def test_production_fidelity_preserves_exhausted_retry_attention(self):
        p, _ = self.environment_image(with_identity_reference=True)
        self.s.mutate(p['id'], None, lambda project: project['shots'][0].update(quality_retry_exhausted={'image':True}))
        self.assertEqual(self.s.next_action(p['id'])['action'], 'quality_attention')

    def test_skipping_optional_checks_does_not_waive_required_reference_fidelity(self):
        p, a = self.environment_image(with_identity_reference=True)
        self.assertEqual(p['calibration']['history'][-1]['scope'], ['style', 'layout'])
        p = self.s.set_calibration_mode(p['id'], 'production', p['revision'], 'user')
        p = self.s.update_production(p['id'], {'require_recorded_checks': False}, p['revision'], 'user')
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'record_quality')
        self.assertIn('Reference fidelity: identity', action['criteria'])
        p = self.inspect(p, a)
        self.assertEqual(self.s.next_action(p['id'])['step'], 'final_review')
        self.assertEqual(len(p['jobs']), 1)
        self.assertEqual(p['calibration']['history'][1]['scope'], ['style', 'layout'])


if __name__ == '__main__': unittest.main()
