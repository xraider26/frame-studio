import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from studio.workflow import Studio
from studio.store import StudioError
from studio.generators import prompt_for
from studio.calibration import style_contract_signature, technical_passed


class ExecutionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.s = Studio(root/'db', root/'media', root/'inbox')
        self.p = self.s.create_project('Trace fixture', 'image-custom', output_type='image')
        self.p = self.s.update_settings(self.p['id'], {'image_model': 'fixture-v1', 'creative_intake': {'vision': 'Amber garden', 'art_style': 'Painterly', 'purpose': 'A cover'}}, self.p['revision'], 'user')
        for step in ['brief', 'script']:
            self.p = self.s.complete_step(self.p['id'], step, {'text': step}, self.p['revision'], 'user')
        self.p = self.s.update_shots(self.p['id'], [{'title': 'Garden', 'image_prompt': 'Amber flowers'}], self.p['revision'], 'user')

    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('studio.execution_evidence'), 'Exact execution evidence module is missing')
        from studio import execution_evidence
        return execution_evidence

    def claim(self):
        return self.s.claim_next(self.p['id'], 'agent:test', 'trace')['job']

    def request(self, job):
        return {'tool': 'fixture-generator', 'prompt': job['handoff']['prompt'], 'negative_prompt': job['handoff']['negative_prompt'], 'references': copy.deepcopy(job['handoff']['references']), 'arguments': {'fixture': True}}

    def record(self, job, request=None, actor='agent:test'):
        self.assertTrue(hasattr(self.s, 'record_generation_execution'), 'Missing owner-bound execution recorder')
        return self.s.record_generation_execution(job['id'], request or self.request(job), self.s.get(self.p['id'])['revision'], actor)

    def return_take(self, job):
        file = self.s.inbox/'fixture.png'; Image.new('RGB', (32, 18), 'orange').save(file)
        return self.s.return_result(job['id'], str(file), 'agent:test')['asset']

    def test_exact_execution_and_line_endings_only(self):
        m = self.module(); job = {'handoff': {'prompt': 'A\nB  C', 'negative_prompt': 'avoid', 'references': []}}
        execution = {'prompt': 'A\r\nB  C', 'negative_prompt': 'avoid', 'references': []}
        self.assertEqual(m.validate_execution(job, execution)['state'], 'match')
        for text in ['A\nB C', 'A B  C', 'A\nB  C ', 'a\nB  C']:
            execution['prompt'] = text
            self.assertEqual(m.validate_execution(job, execution)['prompt_match'], 'mismatch')

    def test_reference_versions_order_and_missing_negative_are_not_equivalent(self):
        m = self.module(); job = {'handoff': {'prompt': 'A', 'negative_prompt': 'avoid', 'references': [{'id': 'a', 'version': 2, 'slot': 'subject'}]}}
        request = {'prompt': 'A', 'negative_prompt': 'avoid', 'references': [{'id': 'a', 'version': 1, 'slot': 'subject'}]}
        self.assertEqual(m.validate_execution(job, request)['references_match'], 'mismatch')
        request.update(references=job['handoff']['references'], negative_prompt='')
        self.assertEqual(m.validate_execution(job, request)['state'], 'mismatch')
        self.assertEqual(m.validate_execution(job, {})['state'], 'unavailable')

    def test_owned_revision_checked_record_preserves_handoff_and_attributes(self):
        job = self.claim(); original = copy.deepcopy(job['handoff']); signature = style_contract_signature(self.p)
        with self.assertRaises(StudioError) as caught: self.record(job, actor='agent:forged')
        self.assertEqual(caught.exception.code, 'job_owner')
        self.record(job)
        stored = self.s.find_job(job['id'])[1]
        self.assertEqual(stored['execution']['evidence_source'], 'agent_reported')
        self.assertEqual(stored['execution']['validation']['state'], 'match')
        self.assertTrue(stored['execution']['request_hash'])
        self.assertEqual(stored['handoff'], original)
        self.assertEqual(style_contract_signature(self.s.get(self.p['id'])), signature)
        with self.assertRaises(StudioError): self.s.record_generation_execution(job['id'], self.request(job), self.p['revision'], 'agent:test')

    def test_external_cannot_forge_server_evidence_or_overwrite_submitted_request(self):
        job = self.claim(); request = self.request(job); request['evidence_source'] = 'server_recorded'
        with self.assertRaises(StudioError): self.record(job, request)
        self.record(job)
        request = self.request(job); request['prompt'] += ' changed'
        with self.assertRaises(StudioError): self.record(job, request)

    def test_missing_or_changed_execution_retains_real_output_as_needs_review(self):
        for altered in [False, True]:
            with self.subTest(altered=altered):
                self.setUp(); job = self.claim()
                if altered:
                    request = self.request(job); request['prompt'] += ' silent rewrite'; self.record(job, request)
                a = self.return_take(job)
                self.assertTrue(Path(a['path']).is_file())
                self.assertEqual(a.get('execution_state'), 'needs_review')
                p = self.s.get(self.p['id']); shot = p['shots'][0]
                self.assertEqual(shot['image_asset'], a['id'])
                self.assertFalse(technical_passed(p, shot, 'image'))
                self.assertEqual(self.s.find_job(job['id'])[1]['status'], 'needs_review')

    def test_recording_missing_evidence_after_return_resolves_without_losing_file(self):
        job = self.claim(); a = self.return_take(job); self.record(job)
        p = self.s.get(self.p['id']); actual = next(x for x in p['assets'] if x['id'] == a['id'])
        self.assertEqual(actual['execution_state'], 'match'); self.assertTrue(Path(actual['path']).is_file())
        self.assertEqual(self.s.find_job(job['id'])[1]['status'], 'succeeded')

    def test_stale_output_and_legacy_job_keep_unavailable_evidence_without_rewriting_v2(self):
        job = self.claim(); original = copy.deepcopy(job['handoff'])
        def legacy(p):
            j = p['jobs'][0]; j['handoff'].pop('execution_contract', None); j['handoff'].pop('rule_application', None)
            p['epoch'] += 1
        self.s.mutate(self.p['id'], None, legacy)
        a = self.return_take(job)
        self.assertTrue(a['stale']); self.assertEqual(a['execution_state'], 'needs_review')
        stored = self.s.find_job(job['id'])[1]
        self.assertNotIn('execution_contract', stored['handoff'])
        self.assertEqual(stored['handoff']['schema_version'], original['schema_version'])
        self.assertEqual(a['execution_validation']['evidence_source'], 'unavailable')

    def test_manifests_preserve_attribution_and_media_review_is_pending(self):
        m = self.module(); p = copy.deepcopy(self.p); p['template_id'] = 'ai-film'; p['production']['recipe'] = {'id': 'ai-film', 'version': 1}
        rows = m.build_rule_application(p, p['shots'][0], 'image', 'visual_direction')
        appearance = next(x for x in rows if x['rule_id'] == 'appearance')
        self.assertEqual(appearance['status'], 'applied'); self.assertTrue(appearance['bindings'])
        self.assertEqual(appearance['provenance'], 'review_derived'); self.assertIn('original_page_citations', appearance); self.assertIn('studio_correction', appearance)
        media = next(x for x in rows if x['phase'] == 'media_review')
        self.assertEqual(media['outcome'], 'pending'); self.assertTrue(media['bindings'])

    def test_required_missing_mapping_and_unverified_preconditions_block(self):
        m = self.module()
        contract = {'active': True, 'source_rules': [{'id': 'unknown-required', 'required': True, 'phase': 'pre_generation', 'stage': ['visual_direction'], 'predicate': {'kind': 'always'}}]}
        with patch('studio.recipes.recipe_context', return_value=contract):
            rows = m.build_rule_application(self.p, self.p['shots'][0], 'image', 'visual_direction')
            self.assertEqual(rows[0]['status'], 'unverified'); self.assertTrue(m.rule_blockers(rows, 'visual_direction'))
        contract['source_rules'][0]['required'] = False
        with patch('studio.recipes.recipe_context', return_value=contract):
            self.assertFalse(m.rule_blockers(m.build_rule_application(self.p, self.p['shots'][0], 'image', 'visual_direction'), 'visual_direction'))

    def test_required_capability_prerequisite_blocks_before_provider(self):
        m = self.module(); contract = {'active': True, 'source_rules': [{'id': 'capabilities', 'required': True, 'phase': 'pre_generation', 'stage': ['visual_direction'], 'predicate': {'kind': 'always'}}]}
        with patch('studio.recipes.recipe_context', return_value=contract):
            rows = m.build_rule_application(self.p, self.p['shots'][0], 'image', 'visual_direction')
            self.assertEqual(rows[0]['status'], 'unverified')
            self.assertIsNone(self.claim())
        self.assertFalse(self.s.get(self.p['id'])['jobs'])

    def test_predicate_not_agent_assertions_controls_scope(self):
        m = self.module(); rule = {'id': 'identity', 'required': True, 'phase': 'pre_generation', 'stage': ['visual_direction'], 'predicate': {'kind': 'reference_purposes', 'purposes': ['identity', 'product']}, 'status': 'not_applicable'}
        with patch('studio.recipes.recipe_context', return_value={'active': True, 'source_rules': [rule]}):
            row = m.build_rule_application(self.p, self.p['shots'][0], 'image', 'visual_direction')[0]
            self.assertEqual(row['status'], 'not_applicable'); self.assertFalse(row['predicate_result']['applicable'])
            p = copy.deepcopy(self.p); p['production']['reference_requirements'] = [{'entity_id': '', 'kind': 'product', 'purpose': 'product', 'required': True, 'source_rule': 'identity', 'asset_ids': []}]
            row = m.build_rule_application(p, p['shots'][0], 'image', 'visual_direction')[0]
            self.assertEqual(row['status'], 'unverified'); self.assertTrue(row['predicate_result']['applicable'])

    def test_external_edit_rules_only_gate_the_relevant_delivery_stage(self):
        m = self.module(); contract = {'active': True, 'source_rules': [{'id': 'unknown-edit', 'required': True, 'phase': 'external_edit', 'stage': ['editor_handoff'], 'predicate': {'kind': 'video'}}]}
        with patch('studio.recipes.recipe_context', return_value=contract):
            rows = m.build_rule_application(self.p, self.p['shots'][0], 'video', 'visual_direction')
            self.assertFalse(m.rule_blockers(rows, 'visual_direction'))
            self.assertTrue(m.rule_blockers(rows, 'editor_handoff'))

    def test_custom_syntax_exact_text_and_environment_contributions_remain_exact(self):
        p = copy.deepcopy(self.p); p['settings'].update(image_generator='custom', custom_image_template='{{native}}\n{subject} ::1.25 --raw ')
        p['shots'][0]['image_prompt'] = 'A. B  C'
        self.assertEqual(prompt_for(p, p['shots'][0], 'image')['prompt'], '{native}\nA. B  C ::1.25 --raw')
        p['settings']['image_generator'] = 'general_image'; p['shots'][0]['direction']['image']['exact_text'] = 'A. B  C!'
        prompt = prompt_for(p, p['shots'][0], 'image')['prompt']; self.assertIn('"A. B  C!"', prompt)


    def test_effective_request_preserves_unsupported_tool_constraints(self):
        m = self.module(); prepared = prompt_for(self.p, self.p['shots'][0], 'image')
        c = m.execution_contract(prepared, [], {'tool_name': 'image_gen.imagegen', 'model': None})
        self.assertEqual(c['compiled_prompt'], prepared['prompt'])
        self.assertEqual(c['compiled_negative_prompt'], prepared['negative_prompt'])
        self.assertTrue(any(x['field'] == 'negative_prompt' for x in c['unsupported_constraints']))

    def test_environment_and_duplicate_entity_contributions_are_deduplicated(self):
        p = copy.deepcopy(self.p); shot = p['shots'][0]
        shot['direction']['environment'] = 'Amber greenhouse'
        shot['direction']['action']['visible_entities'] = ['room', 'room']
        p['production']['bible'] = [{'id':'room','name':'Greenhouse','identity':'','wardrobe':'','layout':'Amber greenhouse','light_sources':'Window','materials':'Glass','voice':''}]
        result = prompt_for(p, shot, 'image')
        self.assertEqual(result['prompt'].count('Amber greenhouse'), 1)
        self.assertIn('prompt_contributions', result)

    def test_generated_prompt_preserves_subject_punctuation_and_exact_text(self):
        p = copy.deepcopy(self.p); shot = p['shots'][0]
        shot['image_prompt'] = 'A.  B; C 3.5 ::2'
        self.assertIn('A.  B; C 3.5 ::2', prompt_for(p, shot, 'image')['prompt'])


    def test_request_arguments_cannot_contradict_reported_prompt_or_upload_paths(self):
        m = self.module(); job = {'handoff': {'prompt':'Amber', 'negative_prompt':'', 'references':[{'id':'a','slot':'s','version':1,'path':'actual.png'}]}}
        request = {'prompt':'Amber','negative_prompt':'','references':job['handoff']['references'], 'arguments': {'prompt':'Blue','referenced_image_paths':['other.png']}}
        result = m.validate_execution(job, request)
        self.assertEqual(result['prompt_match'], 'mismatch'); self.assertEqual(result['references_match'], 'mismatch')

    def test_managed_image_tool_cannot_claim_a_separate_negative_argument(self):
        m = self.module(); job = {'handoff': {'prompt':'Amber', 'negative_prompt':'avoid', 'references':[]}}
        request = {'tool':'image_gen.imagegen','prompt':'Amber','negative_prompt':'avoid','references':[], 'arguments':{'prompt':'Amber','transparent_background':False}}
        self.assertEqual(m.validate_execution(job, request)['state'], 'mismatch')

    def test_json_adapter_records_the_exact_payload_automatically(self):
        import asyncio, base64, io, httpx
        from studio.providers import Providers
        job = self.claim()
        contract = self.s.get_workflow_contract(self.p['id'])
        self.s.acknowledge_workflow_contract(self.p['id'], contract['contract_version'], self.s.get(self.p['id'])['revision'], 'agent:test')
        def running(p): p['jobs'][0].update(status='running', executor='fixture')
        self.s.mutate(self.p['id'], None, running)
        image = io.BytesIO(); Image.new('RGB', (32,18), 'orange').save(image, format='PNG')
        submitted = []
        def respond(request):
            import json
            submitted.append(json.loads(request.content))
            return httpx.Response(200, json={'status':'succeeded','output':{'base64':base64.b64encode(image.getvalue()).decode(),'mime_type':'image/png'}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        providers = Providers(self.s, Path(self.tmp.name)/'connections.json')
        with patch('studio.providers.httpx.AsyncClient', return_value=client):
            asyncio.run(providers._run(job['id'], {'id':'fixture','name':'Fixture','base_url':'https://fixture.invalid','api_key':''}))
        stored = self.s.find_job(job['id'])[1]
        self.assertEqual(stored['status'], 'succeeded')
        self.assertEqual(stored['execution']['evidence_source'], 'server_recorded')
        self.assertEqual(stored['execution']['arguments']['request'], submitted[0])
        self.assertEqual(stored['execution']['validation']['state'], 'match')

    def test_changed_required_rule_prevents_all_provider_requests(self):
        import asyncio
        from studio.providers import Providers
        job = self.claim()
        self.s.mutate(self.p['id'], None, lambda p: p['jobs'][0].update(status='running'))
        providers = Providers(self.s, Path(self.tmp.name)/'connections.json')
        from studio.recipes import recipe_context
        contract = recipe_context(self.p, self.p['shots'][0]); contract['source_rules'].append({'id':'unknown-required','required':True,'phase':'pre_generation','stage':['visual_direction'],'predicate':{'kind':'always'}})
        with patch('studio.recipes.recipe_context', return_value=contract), patch('studio.providers.httpx.AsyncClient') as client:
            asyncio.run(providers._run(job['id'], {'id':'fixture','name':'Fixture','base_url':'https://fixture.invalid','api_key':''}))
            client.assert_not_called()
        self.assertEqual(self.s.find_job(job['id'])[1]['status'], 'failed')


    def test_required_mapping_must_reach_the_actual_custom_template(self):
        m = self.module(); p = copy.deepcopy(self.p)
        p['settings'].update(image_generator='custom', custom_image_template='{subject}')
        rows = m.build_rule_application(p, p['shots'][0], 'image', 'visual_direction')
        framing = next(r for r in rows if r['rule_id'] == 'framing')
        self.assertEqual(framing['status'], 'unverified')
        self.assertIn(framing, m.rule_blockers(rows, 'visual_direction'))


    def test_media_mapping_uses_the_actual_scoped_technical_check_names(self):
        from studio.calibration import default_calibration
        from studio.production import criteria_for
        p = copy.deepcopy(self.p); p['calibration'] = default_calibration()
        p['template_id'] = 'ai-film'; p['production']['recipe'] = {'id':'ai-film','version':1}
        rows = self.module().build_rule_application(p, p['shots'][0], 'image', 'visual_direction')
        required = set(criteria_for(p, p['shots'][0], 'image'))
        self.assertTrue(all(b['criterion'] in required for r in rows if r['phase']=='media_review' for b in r['bindings']))

    def test_external_edit_missing_mapping_blocks_automatic_completion(self):
        p = copy.deepcopy(self.p); p['output_type'] = 'video'
        for step in ['brief','script','visual_direction','pilot','production']:
            p['steps'][step] = {'ready':True,'status':'auto_proceeded'}
        with self.s.connect() as conn:
            import json
            conn.execute('UPDATE studio_projects SET payload=? WHERE id=?',(json.dumps(p),p['id']))
        from studio.recipes import recipe_context
        contract = recipe_context(p, p['shots'][0]); contract['source_rules'].append({'id':'unknown-edit','required':True,'phase':'external_edit','stage':['editor_handoff'],'predicate':{'kind':'video'}})
        with patch('studio.recipes.recipe_context', return_value=contract):
            with self.assertRaises(StudioError) as caught:
                self.s.complete_step(p['id'], 'editor_handoff', {'text':'External editing directions'}, p['revision'], 'user')
            self.assertEqual(caught.exception.code, 'execution_rules_blocked')


    def test_initial_and_later_mutable_continuity_have_distinct_applicability(self):
        p = copy.deepcopy(self.p); p['template_id']='ai-film'; p['production']['recipe']={'id':'ai-film','version':1}
        p['output_type']='video'; shot=p['shots'][0]
        def state_row(target): return next(r for r in self.module().build_rule_application(p,target,'video','pilot') if r['rule_id']=='state')
        self.assertEqual(state_row(shot)['status'], 'not_applicable')
        shot['direction']['action']['state_after']={'door':'closed'}
        later=copy.deepcopy(shot);later['id']='later';later['direction']['action']['state_after']={};p['shots'].append(later)
        self.assertEqual(state_row(later)['status'], 'unverified')
        later['direction']['action']['state_before']={'door':'closed'}
        self.assertEqual(state_row(later)['status'], 'applied')

    def test_builtin_selection_discloses_unexposed_controls_under_creator_tool_label(self):
        prepared=prompt_for(self.p,self.p['shots'][0],'image')
        contract=self.module().execution_contract(prepared,[],{'executor':'agent_builtin','tool_name':'Built-in image tool','model':None})
        self.assertTrue(any(x['field']=='negative_prompt' for x in contract['unsupported_constraints']))


    def test_required_media_rules_need_mapping_but_not_a_fabricated_outcome(self):
        contract={'active':True,'image_checks':[],'video_checks':[],'source_rules':[{'id':'unknown-media','required':True,'phase':'media_review','stage':['visual_direction'],'predicate':{'kind':'always'}}]}
        with patch('studio.recipes.recipe_context',return_value=contract):
            rows=self.module().build_rule_application(self.p,self.p['shots'][0],'image','visual_direction')
            self.assertEqual(rows[0]['status'],'unverified')
            self.assertTrue(self.module().rule_blockers(rows,'visual_direction'))

    def test_custom_video_template_native_syntax_is_preserved_too(self):
        p=copy.deepcopy(self.p);shot=p['shots'][0]
        p['settings'].update(video_generator='custom',custom_video_template='{subject}  ::1.25 .  {{raw}} {motion}')
        shot['motion_prompt']='A.  B'
        self.assertEqual(prompt_for(p,shot,'video')['prompt'],'Amber flowers  ::1.25 .  {raw} A.  B')


    def test_static_appearance_cannot_satisfy_required_mutable_state(self):
        p=copy.deepcopy(self.p);p['template_id']='ai-film';p['production']['recipe']={'id':'ai-film','version':1};p['output_type']='video'
        p['settings']['continuity']='Amber coat and green eyes'
        later=copy.deepcopy(p['shots'][0]);later['id']='later';p['shots'].append(later)
        rows=self.module().build_rule_application(p,later,'video','production')
        state=next(r for r in rows if r['rule_id']=='state')
        self.assertEqual(state['status'],'unverified');self.assertIn(state,self.module().rule_blockers(rows,'production'))
        later['direction']['action']['state_before']={'door':'closed'}
        state=next(r for r in self.module().build_rule_application(p,later,'video','production') if r['rule_id']=='state')
        self.assertEqual(state['status'],'applied')
        self.assertTrue(all(b.get('state_contributions') for b in state['bindings']))

    def test_empty_planning_values_cannot_satisfy_required_claims(self):
        p=copy.deepcopy(self.p);p['template_id']='ugc';p['production']['recipe']={'id':'ugc','version':1}
        self.assertTrue(p['documents']['brief']['text'], 'Unrelated populated brief must not waive factual evidence')
        for empty in ['', '  ', [], {}, {'unverified':''}]:
            with self.subTest(empty=empty):
                p['production']['brief']['factual_sources']=empty
                rows=self.module().build_rule_application(p,p['shots'][0],'image','visual_direction')
                claims=next(r for r in rows if r['rule_id']=='claims')
                self.assertEqual(claims['status'],'unverified');self.assertIn(claims,self.module().rule_blockers(rows,'visual_direction'))
        p['production']['brief']['factual_sources']='Creator-supplied product specification: washable fabric.'
        claims=next(r for r in self.module().build_rule_application(p,p['shots'][0],'image','visual_direction') if r['rule_id']=='claims')
        self.assertEqual(claims['status'],'applied')


if __name__ == '__main__': unittest.main()
