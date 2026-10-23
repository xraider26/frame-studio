import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from studio.workflow import Studio, StudioError


class NextBetaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.studio = Studio(self.root / 'db.sqlite', self.root / 'media', self.root / 'inbox')

    def project(self, output_type='video'):
        p = self.studio.create_project('Creator project', 'custom', output_type=output_type)
        # These tests concern workflow/media, independently of the creator interview.
        return self.studio.update_settings(p['id'], {'image_model': 'Test image model', 'video_model': 'Test video model', 'creative_intake': {'vision': 'A quiet forest', 'art_style': 'Watercolour', 'purpose': 'Art print'}}, p['revision'], 'user')

    def image(self):
        path = self.studio.inbox / 'real.png'
        Image.new('RGB', (32, 32), 'green').save(path)
        return str(path)

    def test_new_projects_saved_creation_batches_and_duplicates_start_without_approval_gates(self):
        p = self.project()
        self.assertFalse(any(p['approval_policy'].values()))
        p = self.studio.set_policy(p['id'], {'brief': True}, p['revision'])
        saved = self.studio.save_project_template(p['id'], 'Reviewed workflow', '', ['workflow'], p['revision'])
        created = self.studio.create_project('From saved', saved['id'])
        self.assertFalse(any(created['approval_policy'].values()))
        clone = self.studio.duplicate_project(p['id'], 'Copy', 'user')
        self.assertFalse(any(clone['approval_policy'].values()))
        batch = self.studio.create_batch('Batch', 'An idea', 'variations', saved['id'], 1, 'batch', 'user')
        self.assertFalse(any(self.studio.get(batch['project_ids'][0])['approval_policy'].values()))
        applied = self.studio.apply_project_template(created['id'], saved['id'], ['workflow'], created['revision'], saved['revision'], 'user')
        self.assertTrue(applied['approval_policy']['brief'])

    def test_image_workflow_reaches_actual_image_final_review_without_video_or_editor(self):
        p = self.project('image')
        p = self.studio.update_production(p['id'], {'recipe': {}, 'require_recorded_checks': False}, p['revision'], 'user')
        for step in ['brief', 'script']:
            p = self.studio.complete_step(p['id'], step, {'text': 'Actual concept'}, p['revision'], 'user')
        p = self.studio.update_shots(p['id'], [{'title': 'Forest', 'image_prompt': 'Watercolour forest'}], p['revision'], 'user')
        preview = self.studio.preview_shot(p['id'], p['shots'][0]['id'])
        self.assertNotIn('video', preview)
        task = self.studio.claim_next(p['id'], 'agent', 'image')
        self.assertEqual(task['handoff']['model'], 'Test image model')
        self.assertEqual(task['handoff']['model_guidance']['model'], 'Test image model')
        self.assertEqual(task['handoff']['creative_intent']['vision'], 'A quiet forest')
        self.studio.return_result(task['job']['id'], self.image(), 'agent')
        p = self.studio.get_project(p['id'])
        self.assertEqual(p['next_action']['step'], 'final_review')
        self.assertEqual(p['jobs'][0]['kind'], 'image')
        p = self.studio.complete_step(p['id'], 'final_review', {'text': 'Selected image inspected'}, p['revision'], 'user')
        self.assertEqual(self.studio.next_action(p['id'])['action'], 'complete')
        self.assertEqual(p['documents']['final_review']['export_asset_ids'], [p['shots'][0]['image_asset']])
        for step in ['pilot', 'production', 'editor_handoff']:
            self.assertEqual(p['steps'][step]['status'], 'skipped')
        with self.assertRaises(StudioError):
            self.studio.editor_handoff(p['id'])
        exported = self.studio.export_handoff(p['id'])
        with zipfile.ZipFile(exported['path']) as archive:
            self.assertTrue(any(n.startswith('images/') for n in archive.namelist()))
            manifest = json.loads(archive.read('manifest.json'))
            self.assertNotIn('video', manifest['shots'][0]['expected_outputs'])

    def test_external_take_is_unselected_real_media_with_unknown_cost_and_no_fabricated_job(self):
        p = self.project('image')
        shot_id = p['shots'][0]['id']
        p = self.studio.import_external_take(p['id'], p['revision'], shot_id, self.image(), 'image', 'user', {'generator': 'Local artist', 'prompt': 'Forest'})
        self.assertEqual(p['jobs'], [])
        self.assertIsNone(p['shots'][0]['image_asset'])
        asset = p['assets'][0]
        self.assertEqual(asset['provenance']['type'], 'externally_created')
        self.assertIsNone(asset['cost']['actual'])
        self.assertEqual(self.studio.production_metrics(p['id'])['unknown_cost_imports'], 1)
        p = self.studio.select_take(p['id'], asset['id'], p['revision'], 'user')
        self.assertEqual(p['shots'][0]['image_asset'], asset['id'])
        with self.assertRaises(StudioError):
            self.studio.import_external_take(p['id'], p['revision'] - 1, shot_id, self.image(), 'image', 'user')
        self.assertEqual(len(self.studio.get(p['id'])['assets']), 1)

    def test_reference_import_binds_entity_atomically_and_increments_version(self):
        p = self.project()
        p = self.studio.update_production(p['id'], {'bible': [{'id': 'hero', 'kind': 'character', 'name': 'Hero'}]}, p['revision'], 'user')
        p = self.studio.import_reference(p['id'], self.image(), 'Hero reference', p['revision'], 'user', entity_id='hero')
        self.assertEqual(p['production']['bible'][0]['asset_ids'], [p['assets'][0]['id']])
        self.assertEqual(p['production']['bible'][0]['version'], 2)
        before = p['revision']
        with self.assertRaises(StudioError):
            self.studio.import_reference(p['id'], self.image(), 'Wrong entity', p['revision'], 'user', entity_id='missing')
        self.assertEqual(self.studio.get(p['id'])['revision'], before)

    def test_legacy_policy_preserved_and_video_only_gates_do_not_block_image_project(self):
        p = self.project('image')
        self.assertEqual(len(p['shots']), 1)
        p = self.studio.update_shots(p['id'], [{**p['shots'][0], 'direction': {'generation_mode': 'motion_control', 'action': {'beats': [{'start': 0, 'end': 99, 'description': 'Video action'}]}}, 'edit_duration_seconds': 99}], p['revision'], 'user')
        self.assertEqual(self.studio.validate_project(p['id'])['errors'], 0)
        def legacy(current):
            current.pop('output_type', None)
            current.pop('creative_intake_required', None)
            current['approval_policy']['brief'] = True
        p = self.studio.mutate(p['id'], p['revision'], legacy)
        loaded = self.studio.get_project(p['id'])
        self.assertEqual(loaded['output_type'], 'video')
        self.assertTrue(loaded['approval_policy']['brief'])

    def test_imported_unknown_cost_blocks_hard_batch_budget_without_jobs(self):
        batch = self.studio.create_batch('Art', 'Forest', 'variations', 'custom', 1, 'art', 'user', output_type='image', policy={'budget_limit': 10, 'image_cost': 1, 'cost_evidence': 'Provider pricing'})
        p = self.studio.get(batch['project_ids'][0])
        p = self.studio.import_external_take(p['id'], p['revision'], p['shots'][0]['id'], self.image(), 'image', 'user')
        metrics = self.studio._batch_metrics(batch, [p])
        self.assertEqual(metrics['unknown_cost_jobs'], 1)
        self.assertIsNotNone(self.studio._dispatch_block(p, 'image'))
        self.assertEqual(p['jobs'], [])

    def test_upload_binds_actual_reference_and_rejects_stale_revision_without_orphans(self):
        import io
        from fastapi.testclient import TestClient
        from studio.api import create_app
        app = create_app(self.root / 'api', 'agent', 'browser')
        client = TestClient(app)
        headers = {'Authorization': 'Bearer browser'}
        p = client.post('/studio/v1/command', headers=headers, json={'operation': 'create_project', 'arguments': {'name': 'Image', 'output_type': 'image'}}).json()
        self.assertFalse(any(p['approval_policy'].values()))
        studio = app.state.studio
        p = studio.update_production(p['id'], {'bible': [{'id': 'hero', 'kind': 'character', 'name': 'Hero'}]}, p['revision'], 'user')
        data = {'project_id': p['id'], 'expected_revision': str(p['revision']), 'role': 'reference', 'entity_id': 'hero', 'kind': 'image'}
        content = Path(self.image()).read_bytes()
        result = client.post('/studio/v1/upload', headers=headers, data=data, files={'file': ('hero.png', content, 'image/png')})
        self.assertEqual(result.status_code, 200, result.text)
        saved = result.json()
        self.assertEqual(saved['production']['bible'][0]['version'], 2)
        self.assertEqual(saved['production']['bible'][0]['asset_ids'], [saved['assets'][0]['id']])
        stale = client.post('/studio/v1/upload', headers=headers, data=data, files={'file': ('hero.png', content, 'image/png')})
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(len(studio.get(p['id'])['assets']), 1)
        self.assertEqual(list(studio.inbox.iterdir()), [])

    def test_report_actual_import_cost_settles_budget_with_evidence_and_audit_history(self):
        p = self.project('image')
        p = self.studio.import_external_take(p['id'], p['revision'], p['shots'][0]['id'], self.image(), 'image', 'user')
        key = p['assets'][0]['id']
        with self.assertRaises(StudioError):
            self.studio.record_import_cost(p['id'], key, 0, '', p['revision'], 'user')
        p = self.studio.record_import_cost(p['id'], key, 2.5, 'Actual provider receipt', p['revision'], 'user')
        self.assertEqual(p['assets'][0]['cost']['actual'], 2.5)
        self.assertEqual(self.studio.production_metrics(p['id'])['unknown_cost_imports'], 0)
        p = self.studio.record_import_cost(p['id'], key, 3, 'Corrected provider receipt', p['revision'], 'user')
        self.assertEqual([entry['actual'] for entry in p['assets'][0]['cost_history']], [2.5, 3])
        self.assertEqual(self.studio.production_metrics(p['id'])['reserved_or_spent'], 3)
        self.assertEqual(p['jobs'], [])

    def test_upload_cannot_mutate_a_batch_canonical_entity(self):
        source = self.project()
        source = self.studio.update_production(source['id'], {'bible': [{'id': 'hero', 'kind': 'character', 'name': 'Hero'}]}, source['revision'], 'user')
        batch = self.studio.create_batch('Cast', 'Hero portrait', 'variations', 'custom', 1, 'canonical', 'user', identity_source_project_id=source['id'], source_revision=source['revision'])
        p = self.studio.get(batch['project_ids'][0])
        with self.assertRaises(StudioError) as error:
            self.studio.import_reference(p['id'], self.image(), 'Replacement', p['revision'], 'user', entity_id='hero')
        self.assertEqual(error.exception.code, 'identity_locked')
        saved = self.studio.get(p['id'])
        self.assertEqual(saved['revision'], p['revision'])
        self.assertEqual(saved['assets'], p['assets'])
        self.assertEqual(saved['production']['bible'], p['production']['bible'])

    def test_external_import_requires_a_real_revision_instead_of_silently_skipping_concurrency(self):
        p = self.project('image')
        for revision in [None, True]:
            with self.assertRaises(StudioError):
                self.studio.import_external_take(p['id'], revision, p['shots'][0]['id'], self.image(), 'image', 'user')
        self.assertEqual(self.studio.get(p['id'])['assets'], [])

    def test_image_handoff_exports_actual_references_before_any_outputs_exist(self):
        p = self.project('image')
        p = self.studio.update_production(p['id'], {'bible': [{'id': 'hero', 'kind': 'character', 'name': 'Hero'}]}, p['revision'], 'user')
        p = self.studio.import_reference(p['id'], self.image(), 'Creator reference', p['revision'], 'user', entity_id='hero')
        exported = self.studio.export_handoff(p['id'])
        with zipfile.ZipFile(exported['path']) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertNotIn('video_generator', manifest)
            self.assertIn('README.txt', archive.namelist())
            self.assertIsNone(manifest['shots'][0]['selected_image'])
            relative = manifest['references'][0]['file']
            self.assertEqual(manifest['shots'][0]['reference_files'][0]['file'], relative)
            self.assertEqual(archive.read(relative), Path(p['assets'][0]['path']).read_bytes())
            self.assertNotIn(str(self.studio.media_root), archive.read('manifest.json').decode())
