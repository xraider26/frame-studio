import copy
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from studio.api import create_app
from studio.workflow import Studio
from studio.store import StudioError
from PIL import Image


def selection(kind='image', **changes):
    return dict(executor='agent_builtin' if kind == 'image' else 'external_handoff',
                tool_name='Built-in image tool' if kind == 'image' else 'Future video app',
                profile='general_image' if kind == 'image' else 'flow_veo', model=None,
                model_version_status='managed' if kind == 'image' else 'unknown', connection_id=None,
                selection_source='creator_statement', source_text='Use the built-in images; decide video later.', **changes)


class GenerationSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = Studio(self.root/'db', self.root/'media', self.root/'inbox')

    def project(self, output='video'):
        return self.s.create_project('Setup', 'custom', output_type=output)

    def test_bootstrap_is_read_only_and_generator_question_precedes_creative_intake(self):
        self.assertTrue(hasattr(self.s, 'start_project_setup'), 'Read-only generator bootstrap is missing')
        first = self.s.start_project_setup()
        self.assertEqual(first['status'], 'needs_input')
        self.assertEqual(first['questions'][0]['id'], 'output_type')
        self.assertIn('model_version_status', first['required_selection_fields'])
        self.assertEqual(self.s.list_projects(), [])
        p = self.project('image')
        before = self.s.get(p['id'])
        state = self.s.start_project_setup(p['id'])
        self.assertEqual(len(state['questions']), 1)
        self.assertEqual(state['questions'][0]['media_kinds'], ['image'])
        self.assertNotIn('video', state['questions'][0]['prompt'])
        self.assertEqual(self.s.get(p['id']), before)

    def test_managed_builtin_is_saved_once_and_does_not_require_invented_model(self):
        self.assertTrue(hasattr(self.s, 'set_generation_setup'), 'Selection persistence is missing')
        p = self.project('image')
        setup = {'version': 1, 'image': selection()}
        p = self.s.set_generation_setup(p['id'], setup, p['revision'], 'agent:test')
        self.assertIsNone(p['generation_setup']['image']['model'])
        self.assertEqual(p['generation_setup']['assertion_authority'], 'agent_reported')
        self.assertEqual(self.s.start_project_setup(p['id'])['questions'], [])
        restarted = Studio(self.root/'db', self.root/'media', self.root/'inbox')
        self.assertEqual(restarted.start_project_setup(p['id'])['status'], 'ready')
        self.assertEqual({q['id'] for q in restarted.get_project(p['id'])['creative_intake']['questions']}, {'vision', 'art_style', 'purpose'})

    def test_supplied_choices_on_creation_are_reused_without_second_question(self):
        self.assertTrue(hasattr(self.s, 'set_generation_setup'), 'Selection persistence is missing')
        p = self.s.create_project('Invoked', 'custom', output_type='image', generation_setup={'version': 1, 'image': selection()})
        self.assertEqual(self.s.start_project_setup(p['id'])['status'], 'ready')
        self.assertEqual(self.s.next_action(p['id'])['questions'][0]['id'], 'vision')

    def test_deferred_video_allows_images_but_blocks_video_execution(self):
        self.assertTrue(hasattr(self.s, 'set_generation_setup'), 'Selection persistence is missing')
        p = self.project()
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': selection(), 'video': None}, p['revision'], 'user')
        self.assertEqual(self.s.start_project_setup(p['id'])['missing_media_kinds'], ['video'])
        self.assertEqual(self.s.next_action(p['id'])['questions'][0]['id'], 'vision')
        p = self.s.update_settings(p['id'], {'creative_intake': {'vision': 'A garden', 'art_style': 'Painting', 'purpose': 'A film'}}, p['revision'], 'user')
        for step in ['brief', 'script']:
            p = self.s.complete_step(p['id'], step, {'text': step}, p['revision'], 'user')
        p = self.s.update_shots(p['id'], [{'title': 'Garden', 'image_prompt': 'A painted garden', 'motion_prompt': 'Leaves drift'}], p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'generate')
        def advance(value):
            value['steps']['visual_direction'] = {'ready': True, 'status': 'approved'}
        p = self.s.mutate(p['id'], p['revision'], advance)
        action = self.s.next_action(p['id'])
        self.assertEqual(action['action'], 'ask_creator')
        self.assertEqual(action['kind'], 'video')
        self.assertIsNone(self.s.claim_next(p['id'], 'user', 'video-blocked', p['revision'])['job'])

    def test_partial_change_preserves_image_and_changes_contract_only_for_video(self):
        self.assertTrue(hasattr(self.s, 'set_generation_setup'), 'Selection persistence is missing')
        p = self.project()
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': selection(), 'video': selection('video')}, p['revision'], 'user')
        image = copy.deepcopy(p['generation_setup']['image'])
        version = self.s.get_workflow_contract(p['id'])['contract_version']
        self.s.mutate(p['id'], p['revision'], lambda v: v['production']['capabilities_by_kind']['image'].update(confirmed=True, source='image test'))
        p = self.s.get(p['id'])
        video = selection('video'); video['tool_name'] = 'Other video app'
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'video': video}, p['revision'], 'user')
        self.assertEqual(p['generation_setup']['image'], image)
        self.assertTrue(p['production']['capabilities_by_kind']['image']['confirmed'])
        self.assertFalse(p['production']['capabilities_by_kind']['video']['confirmed'])
        self.assertNotEqual(self.s.get_workflow_contract(p['id'])['contract_version'], version)
        self.assertIn('generation_setup_fingerprint', self.s.get_workflow_contract(p['id'])['project_policy'])

    def test_legacy_fields_and_template_sources_do_not_confirm_new_flow(self):
        self.assertTrue(hasattr(self.s, 'set_generation_setup'), 'Selection persistence is missing')
        p = self.project('image')
        p = self.s.update_settings(p['id'], {'image_model': 'Default', 'creative_intake': {'vision': 'Garden', 'art_style': 'Paint', 'purpose': 'Cover'}}, p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['action'], 'prepare_step')
        self.assertEqual(self.s.start_project_setup(p['id'])['status'], 'needs_input')
        suggestion = selection(); suggestion['selection_source'] = 'template_unconfirmed'
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': suggestion}, p['revision'], 'user')
        self.assertEqual(self.s.next_action(p['id'])['step'], 'generation_setup')
        with self.assertRaises(StudioError) as err:
            self.s.update_shots(p['id'], [{'title': 'Skip', 'image_prompt': 'Skip setup'}], p['revision'], 'agent:test')
        self.assertEqual(err.exception.code, 'generation_setup_required')

    def test_selection_validation_and_stale_revision_are_atomic(self):
        self.assertTrue(hasattr(self.s, 'set_generation_setup'), 'Selection persistence is missing')
        from studio.generation_setup import validate_generation_setup
        p = self.project('image')
        for field, bad in [('executor', 'magic'), ('profile', 'nonexistent'), ('model_version_status', 'invented'), ('selection_source', 'approved_by_agent')]:
            item = selection(); item[field] = bad
            with self.subTest(field=field), self.assertRaises(StudioError):
                validate_generation_setup({'version': 1, 'image': item}, 'image')
        for revision, code in [(None, 'invalid_revision'), (True, 'invalid_revision'), (0, 'revision_conflict')]:
            with self.subTest(revision=revision), self.assertRaises(StudioError) as err:
                self.s.set_generation_setup(p['id'], {'version': 1, 'image': selection()}, revision, 'user')
            self.assertEqual(err.exception.code, code)
        self.assertNotIn('generation_setup', self.s.get(p['id']))

    def test_api_bootstrap_save_before_ack_and_gate_after_ack(self):
        app = create_app(self.root/'api', 'agent', 'human')
        client = TestClient(app)
        def call(op, **args):
            return client.post('/studio/v1/command', headers={'Authorization': 'Bearer agent'}, json={'operation': op, 'arguments': args, 'actor': 'test'})
        initial = call('start_project_setup', output_type='image')
        self.assertEqual(initial.status_code, 200, initial.text)
        caps = call('studio_capabilities').json()
        self.assertEqual(caps['agent_bootstrap'][0], 'start_project_setup')
        p = call('create_project', name='API', output_type='image', generation_setup={'version': 1}).json()
        contract = call('get_workflow_contract', project_id=p['id']).json()
        call('acknowledge_workflow_contract', project_id=p['id'], expected_revision=p['revision'], contract_version=contract['contract_version'])
        response = call('update_production', project_id=p['id'], production={'brief': {'idea': 'Bypass'}}, expected_revision=p['revision'])
        self.assertEqual(response.json().get('error'), 'generation_setup_required')
        response = call('set_generation_setup', project_id=p['id'], setup={'version': 1, 'image': selection()}, expected_revision=p['revision'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(call('start_project_setup', project_id=p['id']).json()['questions'], [])

    def test_new_api_project_requires_generators_even_with_creative_answers(self):
        client = TestClient(create_app(self.root/'default-api', 'agent', 'human'))
        def call(op, **args):
            return client.post('/studio/v1/command', headers={'Authorization': 'Bearer agent'}, json={'operation': op, 'arguments': args})
        p = call('create_project', name='Default public creation', output_type='image', settings={'creative_intake': {'vision': 'Garden', 'art_style': 'Paint', 'purpose': 'Cover'}}).json()
        self.assertIn('generation_setup', p)
        self.assertEqual(call('next_action', project_id=p['id']).json()['step'], 'generation_setup')

    def test_changed_legacy_model_field_reopens_only_its_selection(self):
        p = self.project()
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': selection(), 'video': selection('video')}, p['revision'], 'user')
        image = copy.deepcopy(p['generation_setup']['image'])
        p = self.s.update_settings(p['id'], {'video_model': 'Different actual model'}, p['revision'], 'user')
        self.assertEqual(p['generation_setup']['image'], image)
        self.assertEqual(self.s.start_project_setup(p['id'])['missing_media_kinds'], ['video'])
        self.assertEqual(self.s.start_project_setup(p['id'])['questions'][0]['media_kinds'], ['video'])

    def test_medium_capabilities_can_be_observed_without_cross_confirming_legacy_data(self):
        p = self.project()
        p = self.s.update_production(p['id'], {'capabilities': {'model': 'Old video model', 'confirmed': True, 'source': 'old observation', 'observed_at': '2026-10-24', 'aspects': ['9:16']}}, p['revision'], 'user')
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': selection(), 'video': None}, p['revision'], 'user')
        # Adopting setup retains old evidence but never applies it to a new image tool.
        self.assertTrue(p['production']['capabilities']['confirmed'])
        errors = self.s.validate_project(p['id'])['issues']
        self.assertFalse(any(e['rule'] == 'unsupported_aspect' for e in errors))
        p = self.s.update_production(p['id'], {'capabilities_by_kind': {'image': {'model': 'Observed image tool', 'confirmed': True, 'source': 'Actual tool observation', 'observed_at': '2026-10-24', 'aspects': ['16:9']}}}, p['revision'], 'user')
        self.assertTrue(p['production']['capabilities_by_kind']['image']['confirmed'])
        self.assertFalse(p['production']['capabilities_by_kind']['video']['confirmed'])

    def test_malformed_setup_is_rejected_as_validation_error(self):
        from studio.generation_setup import validate_generation_setup
        for field in ['executor', 'profile', 'model_version_status', 'selection_source']:
            item = selection(); item[field] = []
            with self.subTest(field=field), self.assertRaises(StudioError):
                validate_generation_setup({'version': 1, 'image': item}, 'image')

    def test_template_apply_cannot_retain_confirmation_for_changed_models(self):
        source = self.project('image')
        source = self.s.update_settings(source['id'], {'image_model': 'Template model'}, source['revision'], 'user')
        template = self.s.save_project_template(source['id'], 'Suggested model', '', ['settings'], source['revision'])
        p = self.s.create_project('Confirmed', 'custom', output_type='image', generation_setup={'version': 1, 'image': selection()})
        p = self.s.apply_project_template(p['id'], template['id'], ['settings'], p['revision'], template['revision'], 'user')
        self.assertEqual(self.s.start_project_setup(p['id'])['missing_media_kinds'], ['image'])
        self.assertEqual(p['generation_setup']['image']['selection_source'], 'template_unconfirmed')
        self.assertEqual(self.s.next_action(p['id'])['step'], 'generation_setup')

    def test_public_batch_children_cannot_bypass_generator_questions(self):
        client = TestClient(create_app(self.root/'batch-api', 'agent', 'human'))
        def call(op, **args):
            return client.post('/studio/v1/command', headers={'Authorization': 'Bearer agent'}, json={'operation': op, 'arguments': args})
        batch = call('create_batch', name='Batch', idea='Garden scenes', request_id='setup-batch', count=1, output_type='image').json()
        p = call('get_project', project_id=batch['project_ids'][0]).json()
        self.assertEqual(p['next_action']['step'], 'generation_setup')

    def test_public_duplicate_requires_confirmation_for_new_project(self):
        app = create_app(self.root/'duplicate-api', 'agent', 'human')
        client = TestClient(app)
        def call(op, **args):
            return client.post('/studio/v1/command', headers={'Authorization': 'Bearer human'}, json={'operation': op, 'arguments': args})
        p = call('create_project', name='Original', output_type='image', generation_setup={'version': 1, 'image': selection()}).json()
        clone = call('duplicate_project', project_id=p['id'], name='New project').json()
        self.assertEqual(call('next_action', project_id=clone['id']).json()['step'], 'generation_setup')

    def test_generator_setup_synchronizes_compiler_execution_route(self):
        p = self.project('image')
        p = self.s.update_settings(p['id'], {'generation_mode': 'api'}, p['revision'], 'user')
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': selection()}, p['revision'], 'user')
        self.assertEqual(p['settings']['generation_mode'], 'external_agent')
        self.assertEqual(p['settings']['image_model'], '')

    def test_tool_change_rejects_old_take_even_when_prompt_profile_and_model_match(self):
        p = self.s.create_project('Tool compatibility', 'custom', output_type='image', generation_setup={'version': 1, 'image': selection()})
        output = self.root/'inbox'/'original.png'
        Image.new('RGB', (32, 18), 'orange').save(output)
        p = self.s.import_external_take(p['id'], p['revision'], p['shots'][0]['id'], str(output), 'image', 'user')
        asset = p['assets'][0]
        changed = selection(); changed['tool_name'] = 'Another opaque image tool'
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': changed}, p['revision'], 'user')
        with self.assertRaises(StudioError) as err:
            self.s.select_take(p['id'], asset['id'], p['revision'], 'agent:test')
        self.assertEqual(err.exception.code, 'incompatible_take')
        current = self.s.get(p['id'])
        self.assertTrue(current['assets'][0]['stale'])
        self.assertIsNone(current['shots'][0]['image_asset'])

    def test_video_tool_change_preserves_image_take_compatibility(self):
        p = self.s.create_project('Separate tools', 'custom', generation_setup={'version': 1, 'image': selection(), 'video': selection('video')})
        output = self.root/'inbox'/'image.png'
        Image.new('RGB', (32, 18), 'orange').save(output)
        p = self.s.import_external_take(p['id'], p['revision'], p['shots'][0]['id'], str(output), 'image', 'user')
        asset = p['assets'][0]
        changed = selection('video'); changed['tool_name'] = 'Another video app'
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'video': changed}, p['revision'], 'user')
        p = self.s.select_take(p['id'], asset['id'], p['revision'], 'user')
        self.assertEqual(p['shots'][0]['image_asset'], asset['id'])
        self.assertFalse(p['assets'][0]['stale'])

    def test_owned_output_returns_after_tool_change_but_cannot_be_reselected(self):
        p = self.s.create_project('Owned return', 'custom', output_type='image', generation_setup={'version': 1, 'image': selection()})
        p = self.s.update_settings(p['id'], {'creative_intake': {'vision': 'Garden', 'art_style': 'Painting', 'purpose': 'Cover'}}, p['revision'], 'user')
        for step in ['brief', 'script']:
            p = self.s.complete_step(p['id'], step, {'text': step}, p['revision'], 'user')
        p = self.s.update_shots(p['id'], [{'title': 'Garden', 'image_prompt': 'A painted garden'}], p['revision'], 'user')
        job = self.s.claim_next(p['id'], 'agent:test', 'owned-output', p['revision'])['job']
        p = self.s.get(p['id'])
        changed = selection(); changed['tool_name'] = 'Another opaque image tool'
        p = self.s.set_generation_setup(p['id'], {'version': 1, 'image': changed}, p['revision'], 'user')
        output = self.root/'inbox'/'owned.png'
        Image.new('RGB', (32, 18), 'orange').save(output)
        returned = self.s.return_result(job['id'], str(output), 'agent:test')
        self.assertTrue(returned['asset']['stale'])
        self.assertTrue(Path(returned['asset']['path']).is_file())
        p = self.s.get(p['id'])
        with self.assertRaises(StudioError) as err:
            self.s.select_take(p['id'], returned['asset']['id'], p['revision'], 'agent:test')
        self.assertEqual(err.exception.code, 'incompatible_take')


if __name__ == '__main__':
    unittest.main()
