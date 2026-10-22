import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio.knowledge import knowledge_catalog
from studio.course_rules import verified_course_material


class ShippedCinematographyAssetsTests(unittest.TestCase):
    def test_every_still_technique_ships_a_real_individual_image_and_prompt(self):
        from studio.cinematography import PUBLIC_ROOT
        entries = knowledge_catalog()['entries']
        stills = [e for e in entries if e['category'] in {'camera', 'lens', 'framing', 'lighting'}]
        self.assertEqual(len(stills), 26)
        paths = set()
        for entry in stills:
            sample = entry['visual']['sample']
            image = PUBLIC_ROOT / sample['image'].lstrip('/')
            self.assertEqual(image.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertTrue(sample['prompt'] and sample['caption'])
            paths.add(image)
        self.assertEqual(len(paths), len(stills))


class CinematographyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.public = Path(self.temp.name) / 'public'
        self.assets = self.public / 'cinematography'
        self.assets.mkdir(parents=True)
        self.asset_patch = patch('studio.cinematography.PUBLIC_ROOT', self.public, create=True)
        self.asset_patch.start()
        self.addCleanup(self.asset_patch.stop)

    def manifest(self, image='/cinematography/wide-shot.png', **overrides):
        example = {'id': 'wide-shot', 'image': image, 'prompt': 'Same artisan in a workshop, wide shot.',
                   'caption': 'Room and subject visible', 'comparison_group': 'workshop-v1',
                   'tool': 'built-in image_gen', **overrides}
        manifest = {'schema_version': 1, 'tool': 'built-in image_gen',
                    'scope': 'Teaching stills, not provider output tests.', 'examples': [example]}
        (self.assets / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_samples_are_available_only_when_manifest_and_local_file_agree(self):
        self.manifest()
        self.assertNotIn('sample', knowledge_catalog(category='framing')['entries'][0]['visual'])
        (self.assets / 'wide-shot.png').write_bytes(b'generated fixture image')
        catalog = knowledge_catalog(category='framing')
        sample = catalog['entries'][0]['visual'].get('sample')
        self.assertIsNotNone(sample)
        self.assertEqual(sample['image'], '/cinematography/wide-shot.png')
        self.assertEqual(sample['kind'], 'generated_still')
        self.assertEqual(sample['comparison_group'], 'workshop-v1')
        self.assertTrue(sample['prompt'] and sample['caption'])
        self.assertEqual(catalog['coverage']['sample_count'], 1)
        (self.assets / 'wide-shot.png').unlink()
        self.assertNotIn('sample', knowledge_catalog(category='framing')['entries'][0]['visual'])

    def test_invalid_or_unsafe_manifest_assets_are_never_offered(self):
        (self.public / 'outside.png').write_bytes(b'outside')
        for image in ['https://example.com/a.png', '/cinematography/../outside.png',
                      '/cinematography/%2e%2e/outside.png', '/cinematography/..\\outside.png',
                      '/outside.png', '/cinematography/wide-shot.png?token=secret']:
            with self.subTest(image=image):
                self.manifest(image)
                self.assertNotIn('sample', knowledge_catalog(category='framing')['entries'][0]['visual'])
        (self.assets / 'wide-shot.png').write_bytes(b'generated fixture image')
        self.manifest(prompt='')
        self.assertNotIn('sample', knowledge_catalog(category='framing')['entries'][0]['visual'])
        (self.assets / 'manifest.json').write_text('{broken', encoding='utf-8')
        self.assertEqual(knowledge_catalog()['coverage'].get('sample_count'), 0)

    def test_visual_metadata_cannot_mutate_future_catalogue_responses(self):
        self.manifest()
        (self.assets / 'wide-shot.png').write_bytes(b'generated fixture image')
        first = knowledge_catalog(category='framing')['entries'][0]
        self.assertIn('sample', first['visual'])
        first['visual']['sample']['caption'] = 'Corrupted'
        first['citations'][0]['page'] = -1
        first['source_rule_ids'].clear()
        fresh = knowledge_catalog(category='framing')['entries'][0]
        self.assertEqual(fresh['visual']['sample']['caption'], 'Room and subject visible')
        self.assertGreater(fresh['citations'][0]['page'], 0)
        self.assertTrue(fresh['source_rule_ids'])

    def test_visual_choices_have_original_page_citations_with_scoped_attribution(self):
        sources = {s['source_id']: s for s in verified_course_material()['sources']}
        for category in ['camera', 'lens', 'framing', 'lighting', 'movement']:
            for entry in knowledge_catalog(category=category)['entries']:
                self.assertTrue(entry.get('citations'), entry['id'])
                self.assertIn('Studio-authored', entry['source_note'])
                for citation in entry['citations']:
                    source = sources[citation['source_id']]
                    self.assertIn(citation['page'], source['review_scope']['pages'])
                    self.assertEqual(citation['lesson_url'], source['lesson_url'])

    def test_all_camera_movements_offer_spatial_demonstrations(self):
        entries = knowledge_catalog(category='movement')['entries']
        self.assertEqual(len(entries), 8)
        for entry in entries:
            self.assertEqual(entry['visual'].get('motion'), {
                'id': entry['id'], 'duration_seconds': 6, 'kind': 'spatial_demonstration'})
            self.assertNotIn('sample', entry['visual'])

    def test_coverage_acknowledges_selected_source_verification(self):
        coverage = knowledge_catalog()['coverage']
        self.assertGreater(coverage.get('source_count', 0), 0)
        self.assertIn('selected', coverage['status'].lower())
        self.assertFalse(coverage['full_original_catalogues'])


if __name__ == '__main__':
    unittest.main()
