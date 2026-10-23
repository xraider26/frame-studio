import copy
import unittest
import tempfile
from pathlib import Path

from studio.intake import creative_intake, validate_intake, model_guidance
from studio.store import StudioError
from studio.workflow import Studio
from studio.generators import prompt_for
from studio.recipes import recipe_context


class CreativeIntakeTests(unittest.TestCase):
    def project(self):
        return {'creative_intake_required': True, 'output_type': 'video', 'settings': {
            'image_generator': 'runway_image', 'image_model': 'Gen-4 Image',
            'video_generator': 'flow_veo', 'video_model': 'Veo 3.1',
            'creative_intake': {}, 'style': 'Cinematic realism'}}

    def test_recipe_defaults_do_not_answer_creator_questions(self):
        p = self.project()
        result = creative_intake(p)
        self.assertEqual(result['status'], 'needs_input')
        self.assertEqual({q['id'] for q in result['questions']}, {'vision', 'art_style', 'purpose'})
        self.assertIn('Ask', result['instructions'])

    def test_answers_guide_but_do_not_apply_technical_settings(self):
        p = self.project()
        p['settings']['creative_intake'] = {'vision': 'A lonely astronaut finding a flower', 'art_style': 'Watercolour illustration', 'purpose': 'An illustrated story cover'}
        before = copy.deepcopy(p)
        result = creative_intake(p)
        self.assertEqual(result['status'], 'ready')
        self.assertTrue(result['suggested_setup'])
        self.assertEqual(p, before)
        self.assertIn('Watercolour', result['answers']['art_style'])

    def test_image_project_does_not_ask_for_video_model(self):
        p = self.project()
        p['output_type'] = 'image'
        p['settings']['image_model'] = ''
        p['settings']['video_model'] = ''
        result = creative_intake(p)
        keys = {q['id'] for q in result['questions']}
        self.assertIn('image_model', keys)
        self.assertNotIn('video_model', keys)

    def test_legacy_projects_are_not_newly_blocked(self):
        self.assertEqual(creative_intake({'settings': {}})['status'], 'legacy')

    def test_bad_answers_rejected_and_input_not_mutated(self):
        for value in [{'vision': 3}, {'unexpected': 'value'}, {'art_style': 'x' * 8001}, []]:
            with self.subTest(value=str(value)[:40]), self.assertRaises(StudioError):
                validate_intake(value)
        original = {'vision': '  A quiet garden  '}
        self.assertEqual(validate_intake(original), {'vision': 'A quiet garden'})
        self.assertEqual(original['vision'], '  A quiet garden  ')

    def test_known_model_guidance_and_unknown_model_are_honest(self):
        known = model_guidance('runway_i2v', 'Gen-4.5', 'video')
        self.assertEqual(known['status'], 'documented')
        self.assertIn('motion', known['instructions'].lower())
        unknown = model_guidance('custom', 'My private model', 'image')
        self.assertEqual(unknown['status'], 'custom_unverified')
        self.assertIn('Verify', unknown['instructions'])

    def test_compiled_prompt_carries_exact_model_and_creator_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = Studio(Path(tmp)/'data.db', Path(tmp)/'media', Path(tmp)/'inbox')
            p = studio.create_project('Illustrated cover', 'custom')
            p['settings'].update(image_generator='runway_image', image_model='Gen-4 Image', creative_intake={'vision': 'An astronaut finds a flower', 'art_style': 'Watercolour illustration', 'purpose': 'A book cover'})
            shot = p['shots'][0]
            shot['image_prompt'] = 'An astronaut holding a flower'
            result = prompt_for(p, shot, 'image')
            self.assertEqual(result['model'], 'Gen-4 Image')
            self.assertEqual(result['model_guidance']['status'], 'documented')
            self.assertIn('Watercolour illustration', result['prompt'])
            self.assertIn('book cover', result['prompt'])
            self.assertNotIn('Cinematic realism', result['prompt'])

    def test_motion_profile_uses_appearance_reference_not_static_redescription(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = Studio(Path(tmp)/'data.db', Path(tmp)/'media', Path(tmp)/'inbox')
            p = studio.create_project('Motion', 'custom')
            p['settings'].update(video_generator='runway_i2v', video_model='Gen-4.5')
            shot = p['shots'][0]
            shot.update(image_prompt='A red ceramic vase', motion_prompt='A petal falls')
            result = prompt_for(p, shot, 'video')
            self.assertIn('A petal falls', result['prompt'])
            self.assertNotIn('A red ceramic vase', result['prompt'])
            self.assertEqual(result['model'], 'Gen-4.5')

    def test_image_recipe_contract_has_no_video_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = Studio(Path(tmp)/'data.db', Path(tmp)/'media', Path(tmp)/'inbox')
            p = studio.create_project('Cover', 'custom')
            p['output_type'] = 'image'
            contract = recipe_context(p)
            self.assertNotIn('pilot', contract['stage_instructions'])
            self.assertNotIn('production', contract['stage_instructions'])
            self.assertNotIn('editor_handoff', contract['stage_instructions'])
            self.assertNotIn('video_profile', contract['settings_scope'])


if __name__ == '__main__':
    unittest.main()
