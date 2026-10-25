import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from studio.workflow import Studio
from studio.store import StudioError
from studio.production import criteria_for
from studio.generators import prompt_for


class CourseRecipeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.studio = Studio(root / 'db.sqlite', root / 'media', root / 'inbox')

    def test_catalogue_has_distinct_source_linked_recipes_and_does_not_claim_video_validation(self):
        from studio.recipes import recipe_catalog
        recipes = [r for r in recipe_catalog(detail="full", include_provenance=True) if r['output_type'] == 'video']
        self.assertEqual(len(recipes), 9)
        self.assertEqual(len({r['intent'] for r in recipes}), 9)
        for r in recipes:
            self.assertTrue(r['source_rules'])
            self.assertEqual(len(r['examples']), 3)
            self.assertEqual(r['validation_status'], 'not_video_validated')
            self.assertTrue(all(role['purpose'] and role['quality'] for role in r['roles']))
            self.assertEqual(set(r['stages']), {'brief', 'script', 'visual_direction', 'pilot', 'production', 'editor_handoff', 'final_review'})

    def test_new_projects_use_runtime_adapted_roles_with_specific_checks_and_same_agent_contract(self):
        p = self.studio.create_project('Cup demonstration', 'ugc')
        self.assertEqual(p['production']['recipe']['version'], 1)
        self.assertAlmostEqual(sum(s['edit_duration_seconds'] for s in p['shots']), p['settings']['duration_seconds'])
        self.assertTrue(all(s['direction']['story_purpose'] for s in p['shots']))
        self.assertTrue(p['production']['require_recorded_checks'])
        criteria = criteria_for(p, p['shots'][1], 'video')
        self.assertIn('Product appearance matches the approved reference.', criteria)
        preview = prompt_for(p, p['shots'][1], 'video')
        self.assertEqual(preview['recipe_contract']['shot_role']['id'], 'demonstration')
        self.assertTrue(preview['recipe_contract']['decision_requirements'])
        self.assertEqual(preview['recipe_contract']['version'], 1)
        self.assertIn('Product appearance matches the approved reference.', preview['separate_notes']['acceptance_criteria'])

    def test_legacy_projects_do_not_silently_opt_in_and_explicit_activation_preserves_overrides(self):
        p = self.studio.create_project('Legacy', 'short-drama')
        def legacy(q):
            q['production'].pop('recipe', None)
            q['production']['require_recorded_checks'] = False
            q['shots'][0]['direction']['camera']['lens'] = 'Custom 65mm'
        p = self.studio.mutate(p['id'], p['revision'], legacy)
        self.assertFalse(self.studio.get_project(p['id'])['recipe_context']['active'])
        p = self.studio.activate_recipe(p['id'], p['revision'], 'user')
        self.assertEqual(p['shots'][0]['direction']['camera']['lens'], 'Custom 65mm')
        self.assertFalse(p['production']['require_recorded_checks'], 'Activation must not secretly change human QC policy')
        with self.assertRaises(StudioError):
            self.studio.activate_recipe(p['id'], p['revision'], 'agent:test')
        with self.assertRaises(StudioError):
            self.studio.activate_recipe(p['id'], p['revision'] - 1, 'user')

    def test_recipe_contract_survives_zip_and_saved_template(self):
        p = self.studio.create_project('Film', 'ai-film')
        t = self.studio.save_project_template(p['id'], 'Film recipe', '', ['settings', 'story'], p['revision'])
        q = self.studio.create_project('Reuse', t['id'])
        self.assertEqual(q['production']['recipe'], p['production']['recipe'])
        result = self.studio.export_handoff(q['id'])
        with zipfile.ZipFile(result['path']) as package:
            manifest = json.loads(package.read('manifest.json'))
        self.assertTrue(manifest['recipe_contract']['active'])
        self.assertTrue(manifest['shots'][0]['video']['recipe_contract']['source_rules'])

    def test_wrong_or_future_recipe_version_is_not_silently_reinterpreted(self):
        p = self.studio.create_project('Film', 'ai-film')
        p = self.studio.mutate(p['id'], p['revision'], lambda q: q['production']['recipe'].update(version=999))
        self.assertFalse(self.studio.get_project(p['id'])['recipe_context']['active'])
        self.assertTrue(any(i['rule'] == 'recipe_version' for i in self.studio.validate_project(p['id'])['issues']))

    def test_transferring_a_look_between_formats_preserves_target_recipe_standards(self):
        source = self.studio.create_project('Source ad', 'advertisement')
        saved = self.studio.save_project_template(source['id'], 'Ad look', '', ['settings'], source['revision'])
        target = self.studio.create_project('Podcast with that look', 'podcast')
        target = self.studio.apply_project_template(target['id'], saved['id'], ['settings'], target['revision'], saved['revision'], 'user')
        self.assertEqual(target['production']['recipe']['id'], 'podcast')
        self.assertTrue(self.studio.get_project(target['id'])['recipe_context']['active'])

    def test_every_generated_example_has_prompt_provenance_and_real_local_file(self):
        from studio.recipes import recipe_catalog
        from studio.course_rules import course_coverage
        self.assertTrue(course_coverage()['sha256'])
        for r in recipe_catalog(detail="full", include_provenance=True):
            for e in r['examples']:
                self.assertTrue(e['available'], e['id'])
                self.assertTrue(e['prompt'] and e['why'])

    def test_original_page_citations_resolve_to_the_declared_verification_scope(self):
        from studio.course_rules import course_coverage, verified_course_material, source_rules
        material = verified_course_material()
        sources = {s['source_id']: s for s in material['sources']}
        self.assertFalse(material['coverage']['review_claim_is_independently_verified'])
        self.assertEqual(material['coverage']['original_pdf_pages'], sum(s['page_count'] for s in sources.values()))
        for group in ['principles', 'frameworks', 'corrections']:
            for item in material[group]:
                for citation in item['citations']:
                    source = sources[citation['source_id']]
                    self.assertIn(citation['page'], source['review_scope']['pages'])
                    self.assertTrue(1 <= citation['page'] <= source['page_count'])
                    self.assertEqual(citation['lesson_url'], source['lesson_url'])
        for source in sources.values():
            self.assertRegex(source['sha256'], r'^[a-f0-9]{64}$')
            self.assertNotIn('Signature=', source['lesson_url'])
        rules = source_rules()
        self.assertEqual(len({r['id'] for r in rules}), 19)
        rules[0]['citations'].clear()
        self.assertTrue(course_coverage()['rules'][0]['citations'], 'Callers cannot mutate the shared source ledger')

    def test_agent_cannot_remove_recipe_standards_through_saved_settings(self):
        p = self.studio.create_project('Active recipe', 'ai-film')
        old = self.studio.create_project('Legacy source', 'ai-film')
        old = self.studio.mutate(old['id'], old['revision'], lambda q: q['production'].update(recipe={}))
        t = self.studio.save_project_template(old['id'], 'Legacy look', '', ['settings'], old['revision'])
        with self.assertRaises(StudioError):
            self.studio.apply_project_template(p['id'], t['id'], ['settings'], p['revision'], t['revision'], 'agent:test')
        self.assertTrue(self.studio.get_project(p['id'])['recipe_context']['active'])

    def test_saved_look_and_runtime_are_effective_in_new_project_without_seeding_overrides(self):
        from studio.creative import effective_direction
        p = self.studio.create_project('Look source', 'ai-film')
        def setup(q):
            q['production']['defaults']['camera']['lens'] = 'Custom 65mm'
            q['settings']['duration_seconds'] = 120
        p = self.studio.mutate(p['id'], p['revision'], setup)
        t = self.studio.save_project_template(p['id'], 'Long custom look', '', ['settings'], p['revision'])
        q = self.studio.create_project('Reused look', t['id'])
        self.assertTrue(all(effective_direction(q, s)['camera']['lens'] == 'Custom 65mm' for s in q['shots']))
        self.assertAlmostEqual(sum(s['edit_duration_seconds'] for s in q['shots']), 120)
        self.assertTrue(all(type(s['duration_seconds']) is int and 1 <= s['duration_seconds'] <= 30 for s in q['shots']))


if __name__ == '__main__':
    unittest.main()
