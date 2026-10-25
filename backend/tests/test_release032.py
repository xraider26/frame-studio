import copy
import unittest
import test_calibration as fixtures


class Calibration032Tests(unittest.TestCase):
    setUp = fixtures.CalibrationTests.setUp
    prepare = fixtures.CalibrationTests.prepare
    take = fixtures.CalibrationTests.take
    inspect = fixtures.CalibrationTests.inspect
    approved = fixtures.CalibrationTests.approved

    def test_scene_palette_light_and_materials_do_not_request_new_style_approval(self):
        p, baseline = self.approved()
        shots = copy.deepcopy(p['shots'])
        shots[1]['direction']['art'].update(palette='Vivid emerald', materials='Grass and rock')
        shots[1]['direction']['lighting']['world_source'] = 'Bright midday sky'
        p = self.s.update_shots(p['id'], shots, p['revision'], 'agent:test')
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
        p, asset = self.take(p, 'different-world')
        p = self.inspect(p, asset)
        self.assertNotEqual(self.s.next_action(p['id'])['action'], 'await_calibration_approval')

    def test_unrendered_intake_metadata_does_not_invalidate_baseline(self):
        p, asset = self.approved()
        p = self.s.update_settings(p['id'], {'creative_intake': {**p['settings']['creative_intake'], 'constraints': 'Five changing backgrounds; some rocky and some leafy', 'purpose': 'Changing backdrop'}}, p['revision'], 'agent:test')
        self.assertEqual(p['shots'][0]['image_asset'], asset['id'])
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')

    def test_restore_exact_inputs_and_take_recovers_real_prior_approval(self):
        p, asset = self.approved()
        original = p['settings']['negative_prompt']
        p = self.s.update_settings(p['id'], {'negative_prompt': 'No dark clouds'}, p['revision'], 'user')
        self.assertNotEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
        p = self.s.update_settings(p['id'], {'negative_prompt': original}, p['revision'], 'user')
        p = self.s.select_take(p['id'], asset['id'], p['revision'], 'agent:test')
        self.assertEqual(self.s.get_project(p['id'])['calibration_state']['status'], 'approved')
        self.assertEqual(sum(h['decision']=='approve' for h in p['calibration']['history']), 1)
