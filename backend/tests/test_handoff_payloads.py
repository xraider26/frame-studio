import copy
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from studio.workflow import Studio
from studio.store import StudioError


class HandoffPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.s = Studio(root/'db', root/'media', root/'inbox')
        self.p = self.s.create_project('Public fixture garden', 'image-custom', output_type='image')
        self.p = self.s.update_settings(self.p['id'], {'image_model': 'fixture-v1', 'creative_intake': {'vision': 'Amber garden', 'art_style': 'Painterly', 'purpose': 'A cover'}}, self.p['revision'], 'user')
        for step in ['brief', 'script']:
            self.p = self.s.complete_step(self.p['id'], step, {'text': 'Creator approved '+step}, self.p['revision'], 'user')
        self.p = self.s.update_shots(self.p['id'], [{'title': 'Garden', 'image_prompt': 'Amber flowers with the exact sign: “Welcome”'}], self.p['revision'], 'user')

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('studio.handoffs'), 'Compact transport is missing')
        from studio import handoffs
        return handoffs

    def claim(self):
        return self.s.claim_next(self.p['id'], 'agent:fixture', 'fixture')

    def test_compact_preserves_execution_and_stored_v2(self):
        m = self.module(); raw = self.claim(); before = copy.deepcopy(raw)
        result = m.serialize_claim(raw)
        self.assertEqual(result['schema_version'], 3)
        self.assertNotIn('handoff', result['job'])
        h = result['handoff']; stored = raw['handoff']
        for key in ['prompt', 'negative_prompt', 'references', 'return_inbox', 'execution_contract', 'required_media_checks']:
            self.assertEqual(h[key], stored[key], key)
        for original, compact in zip(stored['rule_application'], h['rule_application']):
            for key in ['rule_id', 'required', 'bindings', 'predicate_result', 'status']:
                self.assertEqual(compact[key], original[key])
            self.assertEqual(compact.get('reason', compact['predicate_result']['reason']), original['reason'])
        self.assertEqual(h['owner'], 'agent:fixture')
        self.assertTrue(h['contract_version']); self.assertIsInstance(h['source_revision'], int)
        self.assertIn('resource_policy', h['project_policy'])
        self.assertNotIn('coverage', h['recipe_contract']); self.assertNotIn('roles', h['recipe_contract'])
        self.assertEqual(raw, before)
        self.assertEqual(self.s.find_job(raw['job']['id'])[1]['handoff']['schema_version'], 2)
        self.assertLessEqual(m.byte_size(result), 12*1024)
        self.assertEqual(m.serialize_claim(raw, 'legacy'), raw)
        retry = m.serialize_claim(self.s.claim_next(self.p['id'], 'agent:fixture', 'fixture', self.p['revision']))
        self.assertEqual(h, retry['handoff'])

    def test_polling_omits_nested_payloads_but_diagnostic_is_complete(self):
        self.module(); raw = self.claim()
        p = self.s.get_project(self.p['id'])
        self.assertNotIn('handoff', p['jobs'][0])
        self.assertNotIn('coverage', p['recipe_context'])
        full = self.s.get_project(self.p['id'], detail='full')
        self.assertEqual(full['jobs'][0]['handoff'], raw['handoff'])

    def test_context_is_hash_addressed_immutable_and_durable(self):
        m = self.module(); raw = self.claim(); h = m.serialize_claim(raw)['handoff']
        ref = h['context_refs']['recipe']
        blob = self.s.get_context(**ref)
        original = copy.deepcopy(blob)
        self.assertEqual(m.content_version(blob['data']), ref['version'])
        blob['data']['intent'] = 'caller mutation'
        self.assertEqual(self.s.get_context(**ref), original)
        restarted = Studio(self.s.db_path, self.s.media_root, self.s.inbox)
        self.assertEqual(restarted.get_context(**ref), original)
        with self.assertRaises(StudioError): self.s.get_context(ref['context_id'], 'wrong-version')

    def test_context_storage_failure_does_not_commit_an_unusable_claim(self):
        revision=self.s.get(self.p['id'])['revision']
        with patch.object(self.s, '_save_contexts', side_effect=RuntimeError('fixture storage failure')):
            with self.assertRaises(RuntimeError): self.claim()
        p=self.s.get(self.p['id'])
        self.assertEqual(len(p['jobs']), 0)
        self.assertEqual(p['revision'],revision)

    def test_oversize_is_diagnostic_before_claim_and_never_truncates(self):
        m = self.module()
        self.s.mutate(self.p['id'], None, lambda p: p['shots'][0].update(image_prompt='X'*70000))
        with self.assertRaises(StudioError) as caught: self.claim()
        self.assertEqual(caught.exception.code, 'payload_too_large')
        self.assertIn('field_bytes', str(caught.exception)); self.assertIn('get_context', str(caught.exception))
        p = self.s.get(self.p['id'])
        self.assertEqual(p['jobs'], []); self.assertEqual(p['shots'][0]['image_prompt'], 'X'*70000)

    def test_applicable_rules_and_blocking_policy_survive_compaction(self):
        m = self.module(); raw = self.claim()
        raw['handoff']['execution_packet']['project_policy']['approval_policy']['final_review'] = True
        raw['handoff']['rule_application'].append({'rule_id': 'adversarial', 'required': True, 'applicable': True, 'reason': 'Must bind explicit source', 'bindings': [{'path': '/fixtures/public.png', 'version': 7}]})
        result = m.serialize_claim(raw)['handoff']
        self.assertTrue(result['project_policy']['approval_policy']['final_review'])
        self.assertEqual(result['rule_application'][-1]['rule_id'], 'adversarial')
        self.assertEqual(result['rule_application'][-1]['bindings'][0]['version'], 7)

    def test_targeted_catalogs_and_bootstrap_budget(self):
        m = self.module()
        from studio.recipes import recipe_catalog
        from studio.sequences import sequence_catalog
        summary = recipe_catalog(limit=2)
        self.assertEqual(len(summary), 2); self.assertNotIn('source_rules', summary[0])
        detail = recipe_catalog(recipe_id='image-custom', stage='visual_direction', role='image-concept', detail='full')
        self.assertEqual(list(detail[0]['stages']), ['visual_direction'])
        self.assertEqual([r['id'] for r in detail[0]['roles']], ['image-concept'])
        self.assertNotIn('provenance', detail[0]['source_rules'][0])
        self.assertEqual(len(sequence_catalog(limit=1)['sequences']), 1)
        contract = self.s.get_workflow_contract(self.p['id'])
        self.assertNotIn('prompting_guide', contract)
        bootstrap = {'contract': contract, 'recipes': recipe_catalog(), 'sequences': sequence_catalog()}
        self.assertLessEqual(m.byte_size(bootstrap), 16*1024)

    def test_fixture_benchmark_uses_minified_utf8(self):
        m = self.module()
        fixture = json.loads((Path(__file__).parent/'fixtures'/'handoff-v3.json').read_text(encoding='utf-8'))
        self.assertLessEqual(m.byte_size(fixture['packet']), 12*1024)
        self.assertLessEqual(m.byte_size(fixture['bootstrap']), 16*1024)
        self.assertEqual(fixture['packet']['handoff']['owner'], 'agent:fixture')
        self.assertIn('rule_application', fixture['packet']['handoff'])

    def test_public_claim_and_targeted_reads_use_compact_default(self):
        from fastapi.testclient import TestClient
        from studio.api import create_app
        root = Path(self.tmp.name)/'api'
        client = TestClient(create_app(root, 'agent', 'human'))
        def call(op, args):
            return client.post('/studio/v1/command', headers={'Authorization': 'Bearer human'}, json={'operation': op, 'arguments': args}).json()
        project = call('create_project', {'name': 'Transport fixture', 'template_id': 'image-custom', 'output_type': 'image', 'settings': self.p['settings']})
        project = call('update_settings', {'project_id': project['id'], 'settings': self.p['settings'], 'expected_revision': project['revision']})
        for step in ['brief', 'script']:
            project = call('complete_step', {'project_id': project['id'], 'step': step, 'output': {'text': step}, 'expected_revision': project['revision']})
        project = call('update_shots', {'project_id': project['id'], 'shots': [{'title': 'Garden', 'image_prompt': 'Amber garden'}], 'expected_revision': project['revision']})
        args = {'project_id': project['id'], 'request_id': 'public', 'expected_revision': project['revision']}
        result = call('claim_generation', args)
        self.assertEqual(result.get('schema_version'), 3, result)
        self.assertNotIn('handoff', result['job'])
        self.assertEqual(result['handoff']['prompt'], call('get_job', {'job_id': result['job']['id'], 'detail': 'full'})['handoff']['prompt'])
        self.assertNotIn('handoff', call('get_job', {'job_id': result['job']['id']}))
        execution = call('get_job', {'job_id': result['job']['id'], 'detail': 'execution'})
        self.assertEqual(execution['handoff']['prompt'], result['handoff']['prompt'])
        self.assertNotIn('coverage', execution['handoff']['recipe_contract'])
        legacy = call('claim_generation', {**args, 'response_format': 'legacy'})
        self.assertEqual(legacy['handoff'], legacy['job']['handoff'])
        ref = result['handoff']['context_refs']['recipe']
        self.assertEqual(call('get_context', ref)['version'], ref['version'])
        self.assertNotIn('source_rules', call('recipe_catalog', {})['recipes'][0])
        self.assertEqual(len(call('source_catalog', {'source_id': 'appearance', 'detail': 'full'})['rules']), 1)
        caps = call('studio_capabilities', {})
        self.assertNotIn('creative_schema', caps)
        self.assertIn('creative_schema', call('studio_capabilities', {'detail': 'full'}))

    def test_provider_rechecks_contract_after_cached_context(self):
        from studio.providers import Providers
        self.module(); raw = self.claim(); job_id = raw['job']['id']
        contract = self.s.get_workflow_contract(self.p['id'])
        self.s.acknowledge_workflow_contract(self.p['id'], contract['contract_version'], self.s.get(self.p['id'])['revision'], 'agent:fixture')
        self.s.mutate(self.p['id'], None, lambda p: p['jobs'][0].update(status='running'))
        provider = Providers(self.s, Path(self.tmp.name)/'providers.json')
        self.s.mutate(self.p['id'], None, lambda p: p['production']['resources'].update(limit=999))
        with self.assertRaises(StudioError) as caught: provider._execution_current(job_id)
        self.assertEqual(caught.exception.code, 'contract_required')

    def test_managed_model_and_unknown_capability_remain_unasserted(self):
        from test_generation_setup import selection
        m = self.module()
        self.p = self.s.set_generation_setup(self.p['id'], {'version': 1, 'image': selection()}, self.p['revision'], 'user')
        raw = self.claim(); h = m.serialize_claim(raw)['handoff']
        self.assertIsNone(h['generator_selection']['model'])
        self.assertIsNone(h['cost']['planned']); self.assertIsNone(h['cost']['actual'])
        self.assertFalse(h['capabilities']['confirmed']); self.assertIsNone(h['capabilities']['audio'])

    def test_historical_v2_serialization_never_rewrites_original(self):
        m = self.module(); raw = self.claim()
        raw['handoff'].pop('execution_packet'); raw['job']['handoff'].pop('execution_packet')
        before = copy.deepcopy(raw)
        result = m.serialize_claim(raw)
        self.assertEqual(raw, before)
        self.assertNotIn('handoff', result['job'])
        self.assertEqual(result['handoff']['prompt'], before['handoff']['prompt'])
        self.assertEqual(result['handoff']['production'], before['handoff']['production'])


if __name__ == '__main__': unittest.main()
