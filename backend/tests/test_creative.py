from workflow_fixtures import CREATOR_SETTINGS, creator_ready
import copy
import tempfile
import unittest
from pathlib import Path

from studio.workflow import Studio
from studio.store import StudioError
from studio.generators import prompt_for


class CreativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.studio = Studio(root / 'db.sqlite', root / 'media', root / 'inbox')
        self.p = self.studio.create_project('Directed film', 'ai-film')
        self.p = creator_ready(self.studio, self.p)
        # Keep the pre-recipe fixture contract; new defaults have dedicated recipe tests.
        def legacy(p):
            p['production'].update(recipe={}, require_recorded_checks=False)
            for s in p['shots']:
                s.update(duration_seconds=4, edit_duration_seconds=4)
        self.p = self.studio.mutate(self.p['id'], self.p['revision'], legacy)

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

    def prepare(self):
        p = self.p
        p = self.studio.set_policy(p['id'], {'brief': False, 'script': False}, p['revision'])
        for step in ['brief', 'script']:
            p = self.studio.complete_step(p['id'], step, {'text': 'A meaningful ' + step}, p['revision'], 'agent')
        p = self.studio.update_shots(p['id'], [{**p['shots'][0], 'image_prompt': 'Traveler in an observatory', 'motion_prompt': 'Turns toward window', 'direction': {'camera': {'lens': '85mm', 'move': 'Locked off'}, 'lighting': {'technique': 'Low key', 'world_source': 'North wall window'}}}], p['revision'], 'agent')
        self.p = p
        return p

    def test_compiler_replaces_defaults_and_export_carries_structured_plan(self):
        p = self.prepare()
        rendered = prompt_for(p, p['shots'][0], 'video')
        self.assertIn('85mm', rendered['prompt'])
        self.assertNotIn('35mm', rendered['prompt'])
        self.assertIn('North wall window', rendered['prompt'])
        self.assertIn('Locked off', rendered['prompt'])
        self.assertNotIn('Slow dolly in', rendered['prompt'])
        exported = self.studio.export_handoff(p['id'])
        self.assertIn('production', exported['manifest'])
        self.assertEqual(exported['manifest']['shots'][0]['direction']['camera']['lens'], '85mm')
        self.assertIn('preflight', exported['manifest'])

    def test_preflight_reports_reference_timing_and_explained_continuity(self):
        p = self.prepare()
        self.assertTrue(hasattr(self.studio, 'validate_project'), 'Missing creative preflight')
        first = p['shots'][0]
        bad = {**first, 'edit_duration_seconds': 6, 'direction': {'references': [{'slot': '1', 'asset_id': 'missing'}], 'sound': {'measured_seconds': 5}, 'action': {'state_after': {'traveler.door': 'closed'}, 'beats': [{'start': 0, 'end': 5, 'description': 'Too long'}]}}}
        second = {'title': 'Reverse', 'duration_seconds': 4, 'image_prompt': 'Reverse angle', 'direction': {'action': {'continuity_from': first['id'], 'state_before': {'traveler.door': 'open'}}}}
        p = self.studio.update_shots(p['id'], [bad, second], p['revision'], 'agent')
        checks = self.studio.validate_project(p['id'])
        rules = {i['rule'] for i in checks['issues']}
        self.assertTrue({'reference_missing', 'edit_exceeds_generation', 'action_timing', 'dialogue_timing', 'continuity_state'} <= rules)
        blocked = self.studio.claim_next(p['id'], 'agent', 'invalid')
        self.assertEqual(blocked['next_action']['action'], 'resolve_preflight')
        self.assertFalse(self.studio.get_project(p['id'])['jobs'])

    def test_handoff_contains_effective_direction_and_current_references(self):
        p = self.prepare()
        handoff = self.studio.claim_next(p['id'], 'agent', 'handoff')['handoff']
        self.assertIn('effective_direction', handoff)
        self.assertEqual(handoff['effective_direction']['camera']['lens'], '85mm')
        self.assertIn('acceptance_criteria', handoff)
        self.assertIn('preflight', handoff)

    def test_explicit_false_can_override_inherited_listener_cutaway(self):
        from studio.creative import effective_direction
        p = self.p
        p['production']['defaults']['sound']['cutaway'] = True
        p['shots'][0]['direction']['sound']['cutaway'] = False
        self.assertFalse(effective_direction(p, p['shots'][0])['sound']['cutaway'])

    def test_duplicate_remaps_bible_reference_and_continuation_ids(self):
        from PIL import Image
        p=self.p
        path=self.studio.inbox/'ref.png';Image.new('RGB',(8,8)).save(path)
        p=self.studio.import_reference(p['id'],str(path),'Canonical traveler',p['revision'],'user')
        asset=p['assets'][0]['id']
        p=self.studio.update_production(p['id'],{'bible':[{'id':'traveler','kind':'character','name':'Traveler','asset_ids':[asset]}]},p['revision'],'user')
        shots=p['shots'];shots[0]['direction']['references']=[{'slot':'portrait','asset_id':asset,'entity_id':'traveler'}]
        shots[1]['direction']['action']['continuity_from']=shots[0]['id']
        p=self.studio.update_shots(p['id'],shots,p['revision'],'user')
        clone=self.studio.duplicate_project(p['id'],'Copy','user')
        new_asset=clone['assets'][0]['id']
        self.assertNotEqual(new_asset,asset)
        self.assertEqual(clone['production']['bible'][0]['asset_ids'],[new_asset])
        self.assertEqual(clone['shots'][0]['direction']['references'][0]['asset_id'],new_asset)
        self.assertEqual(clone['shots'][1]['direction']['action']['continuity_from'],clone['shots'][0]['id'])

    def test_legacy_upgrade_backs_up_and_keeps_existing_look(self):
        import json,sqlite3
        p=copy.deepcopy(self.p);p.pop('production');p.pop('schema_version');p['template_id']='podcast'
        for shot in p['shots']:shot.pop('direction')
        with self.studio.connect() as conn:conn.execute('UPDATE studio_projects SET payload=? WHERE id=?',(json.dumps(p),p['id']))
        reopened=Studio(self.studio.db_path,self.studio.media_root,self.studio.inbox)
        self.assertTrue(self.studio.db_path.with_name('db.pre-creative-v2.sqlite3').exists())
        saved=reopened.get_project(p['id'])
        self.assertIn('Slow dolly in',prompt_for(saved,saved['shots'][0],'video')['prompt'])

    def test_edit_source_range_and_editor_export(self):
        p=self.p
        shot={**p['shots'][0],'duration_seconds':8,'edit_duration_seconds':4,'edit_in_seconds':3}
        p=self.studio.update_shots(p['id'],[shot],p['revision'],'user')
        handoff=self.studio.editor_handoff(p['id'])
        self.assertEqual(handoff['shots'][0]['source_in'],3)
        self.assertEqual(handoff['shots'][0]['source_out'],7)
        from studio.exports import export_editor
        import zipfile
        bundle=export_editor(self.studio,p['id'])
        with zipfile.ZipFile(bundle['path']) as archive:
            self.assertIn('edit-decision.csv',archive.namelist())
        self.assertFalse(bundle['manifest']['ready'])


if __name__ == '__main__':
    unittest.main()
