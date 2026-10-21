import copy
import tempfile
import unittest
from pathlib import Path

from studio.workflow import Studio
from studio.store import StudioError


class CreativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.studio = Studio(root / 'db.sqlite', root / 'media', root / 'inbox')
        self.p = self.studio.create_project('Directed film', 'ai-film')

    def test_nested_direction_survives_an_old_client_edit_and_restart(self):
        p = self.p
        shot = {**p['shots'][0], 'direction': {'camera': {'lens': '85mm', 'move': 'Locked off'}, 'lighting': {'technique': 'Low key', 'world_source': 'Window on north wall'}}}
        p = self.studio.update_shots(p['id'], [shot], p['revision'], 'agent')
        old_client = {k: v for k, v in p['shots'][0].items() if k != 'direction'}
        old_client['title'] = 'Renamed by old client'
        p = self.studio.update_shots(p['id'], [old_client], p['revision'], 'agent')
        reopened = Studio(self.studio.db_path, self.studio.media_root, self.studio.inbox)
        saved = reopened.get_project(p['id'])
        self.assertEqual(saved['shots'][0]['direction']['camera']['lens'], '85mm')
        self.assertEqual(saved['shots'][0]['direction']['lighting']['world_source'], 'Window on north wall')

    def test_production_is_validated_and_roundtrips(self):
        p = self.p
        self.assertTrue(hasattr(self.studio, 'update_production'), 'Missing structured production update')
        p = self.studio.update_production(p['id'], {'brief': {'promise': 'One unsettling discovery'}, 'bible': [{'id': 'traveler', 'kind': 'character', 'name': 'Traveler', 'identity': 'Round glasses', 'version': 1}]}, p['revision'], 'agent')
        self.assertEqual(self.studio.get_project(p['id'])['production']['brief']['promise'], 'One unsettling discovery')
        with self.assertRaises(StudioError):
            self.studio.update_production(p['id'], {'bible': [{'id': 'x', 'kind': 'character', 'name': 'X', 'version': -1}]}, p['revision'], 'agent')

    def test_unknown_direction_fields_and_nonfinite_duration_rejected(self):
        p = self.p
        for direction in [{'camera': {'invented_setting': 'x'}}, {'sound': {'measured_seconds': float('nan')}}]:
            with self.assertRaises(StudioError):
                self.studio.update_shots(p['id'], [{**p['shots'][0], 'direction': direction}], p['revision'], 'agent')

    def test_format_starts_with_relevant_rules_and_source_coverage_is_honest(self):
        p = self.studio.create_project('Interview', 'podcast')
        self.assertIn('production', p, 'Missing format-aware production rules')
        self.assertIn('listener', ' '.join(p['production']['format_rules']).lower())
        from studio.knowledge import knowledge_catalog
        catalog = knowledge_catalog()
        self.assertGreater(len(catalog['entries']), 15)
        self.assertFalse(catalog['coverage']['full_original_catalogues'])
        self.assertTrue(all(e['source'] and e['provenance'] for e in catalog['entries']))


if __name__ == '__main__':
    unittest.main()
