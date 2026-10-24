import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
from studio.api import create_app
from workflow_fixtures import CREATOR_SETTINGS


class AgentContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = create_app(self.root, 'agent', 'human')
        self.client = TestClient(self.app)
        self.p = self.call('create_project', {'name': 'Contract fixture', 'settings': CREATOR_SETTINGS}).json()

    def call(self, op, args=None, human=False, actor='worker'):
        return self.client.post('/studio/v1/command', json={'operation': op, 'arguments': args or {}, 'actor': actor}, headers={'Authorization': 'Bearer ' + ('human' if human else 'agent')})

    def ack(self, actor='worker'):
        contract = self.call('get_workflow_contract', {'project_id': self.p['id']}, actor=actor).json()
        response = self.call('acknowledge_workflow_contract', {'project_id': self.p['id'], 'contract_version': contract['contract_version'], 'expected_revision': contract['revision']}, actor=actor)
        self.assertEqual(response.status_code, 200, response.text)
        return contract

    def complete(self, step='brief', revision='current', actor='worker'):
        return self.call('complete_step', {'project_id': self.p['id'], 'step': step, 'output': {'text': 'Actual document'}, 'expected_revision': self.p['revision'] if revision == 'current' else revision}, actor=actor)

    def test_agent_must_acknowledge_current_contract_without_project_revision_change(self):
        response = self.complete()
        self.assertEqual(response.json().get('error'), 'contract_required', response.text)
        contract = self.ack()
        self.assertTrue(contract['mandatory_rules'])
        self.assertEqual(self.call('get_project', {'project_id': self.p['id']}).json()['revision'], self.p['revision'])
        self.assertEqual(self.complete(actor='other').json().get('error'), 'contract_required')
        self.assertEqual(self.complete().status_code, 200)

    def test_human_policy_change_invalidates_acknowledgement(self):
        old = self.ack()
        self.p = self.call('set_policy', {'project_id': self.p['id'], 'policy': {'brief': True}, 'expected_revision': self.p['revision']}, human=True).json()
        self.assertEqual(self.complete().json().get('error'), 'contract_required')
        self.assertNotEqual(old['contract_version'], self.ack()['contract_version'])
        self.assertEqual(self.complete().status_code, 200)
        self.assertEqual(self.complete().json().get('error'), 'revision_conflict')
        self.assertEqual(self.call('review', {}).json()['error'], 'human_only')

    def test_revision_must_be_explicit_integer_and_current(self):
        self.ack()
        for revision in [None, True, False, '1', 1.0]:
            with self.subTest(revision=revision):
                self.assertEqual(self.complete(revision=revision).json().get('error'), 'invalid_revision')
        self.assertEqual(self.complete(revision=0).json()['error'], 'revision_conflict')

    def test_agent_cannot_skip_intake_or_rewrite_pending_review(self):
        self.p = self.call('create_project', {'name': 'Missing intake'}).json()
        self.ack()
        self.assertEqual(self.complete().json().get('error'), 'step_blocked')
        self.p = self.call('update_settings', {'project_id': self.p['id'], 'settings': CREATOR_SETTINGS, 'expected_revision': self.p['revision']}, human=True).json()
        self.p = self.call('set_policy', {'project_id': self.p['id'], 'policy': {'brief': True}, 'expected_revision': self.p['revision']}, human=True).json()
        self.ack()
        self.p = self.complete().json()
        self.assertEqual(self.complete().json().get('error'), 'step_blocked')
        self.assertEqual(self.complete(step='script').json().get('error'), 'step_blocked')
        response = self.call('complete_step', {'project_id': self.p['id'], 'step': 'brief', 'output': {'text': 'Human edit'}, 'expected_revision': self.p['revision']}, human=True)
        self.assertEqual(response.status_code, 200, response.text)

    def test_existing_claim_return_survives_policy_change_and_claim_retry_is_real(self):
        self.ack()
        for step in ['brief', 'script']:
            self.p = self.complete(step).json()
        self.p = self.call('update_shots', {'project_id': self.p['id'], 'shots': [{'title': 'Cover', 'image_prompt': 'A quiet observatory', 'motion_prompt': 'A star moves'}], 'expected_revision': self.p['revision']}).json()
        args = {'project_id': self.p['id'], 'request_id': 'claim', 'expected_revision': self.p['revision']}
        self.assertEqual(self.call('claim_generation', {**args, 'expected_revision': None}).json().get('error'), 'invalid_revision')
        task = self.call('claim_generation', args).json()
        self.assertIn('job', task, task)
        retry = self.call('claim_generation', args).json()
        self.assertEqual(task['job']['id'], retry['job']['id'])
        self.p = self.call('get_project', {'project_id': self.p['id']}).json()
        self.p = self.call('set_policy', {'project_id': self.p['id'], 'policy': {'visual_direction': True}, 'expected_revision': self.p['revision']}, human=True).json()
        output = self.root / 'inbox' / 'real.png'
        Image.new('RGB', (32, 18), 'orange').save(output)
        returned = self.call('return_generation', {'job_id': task['job']['id'], 'output_path': str(output)})
        self.assertEqual(returned.status_code, 200, returned.text)
        self.assertTrue(Path(returned.json()['asset']['path']).is_file())
    def test_contract_is_persistent_and_changes_only_for_policy_or_models(self):
        contract = self.ack()
        self.p = self.complete().json()
        self.assertEqual(self.call('get_workflow_contract', {'project_id': self.p['id']}).json()['contract_version'], contract['contract_version'])
        restarted = TestClient(create_app(self.root, 'agent', 'human'))
        previous = self.client
        self.client = restarted
        self.assertEqual(self.complete(step='script').status_code, 200)
        self.client = previous
        self.p = self.call('get_project', {'project_id': self.p['id']}).json()
        self.p = self.call('update_settings', {'project_id': self.p['id'], 'settings': {'image_model': 'A different actual model'}, 'expected_revision': self.p['revision']}, human=True).json()
        self.assertEqual(self.call('update_shots', {'project_id': self.p['id'], 'shots': self.p['shots'], 'expected_revision': self.p['revision']}).json()['error'], 'contract_required')
        self.assertNotEqual(self.ack()['contract_version'], contract['contract_version'])

    def test_stale_acknowledgements_and_impersonation_do_not_grant_approval(self):
        contract = self.ack()
        self.p = self.call('set_policy', {'project_id': self.p['id'], 'policy': {'brief': True}, 'expected_revision': self.p['revision']}, human=True).json()
        response = self.call('acknowledge_workflow_contract', {'project_id': self.p['id'], 'contract_version': contract['contract_version'], 'expected_revision': self.p['revision']})
        self.assertEqual(response.json()['error'], 'contract_outdated')
        self.assertEqual(self.call('review', {'project_id': self.p['id'], 'approve': True}, actor='user').json()['error'], 'human_only')
        self.assertEqual(self.call('update_production', {'project_id': self.p['id'], 'production': {'resources': {'limit': None}}}, actor='user').json()['error'], 'human_only')
        self.assertFalse(self.call('get_project', {'project_id': self.p['id']}).json()['steps']['brief']['ready'])

    def test_agent_upload_requires_contract_and_preserves_project_on_rejection(self):
        import io
        data = io.BytesIO()
        Image.new('RGB', (32, 18), 'orange').save(data, format='PNG')
        result = self.client.post('/studio/v1/upload', headers={'Authorization': 'Bearer agent'}, data={'project_id': self.p['id'], 'expected_revision': self.p['revision'], 'role': 'reference'}, files={'file': ('real.png', data.getvalue(), 'image/png')})
        self.assertEqual(result.json()['error'], 'contract_required')
        self.assertEqual(self.call('get_project', {'project_id': self.p['id']}).json()['assets'], [])
    def test_agent_upload_can_use_its_acknowledged_actor(self):
        import io
        self.ack()
        data = io.BytesIO()
        Image.new('RGB', (32, 18), 'orange').save(data, format='PNG')
        result = self.client.post('/studio/v1/upload', headers={'Authorization': 'Bearer agent'}, data={'project_id': self.p['id'], 'expected_revision': self.p['revision'], 'role': 'reference', 'actor': 'worker'}, files={'file': ('real.png', data.getvalue(), 'image/png')})
        self.assertEqual(result.status_code, 200, result.text)
        project = self.call('get_project', {'project_id': self.p['id']}).json()
        self.assertEqual(len(project['assets']), 1)
        self.assertEqual(project['history'][-1]['actor'], 'agent:worker')
