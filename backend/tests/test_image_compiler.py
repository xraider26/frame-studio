import tempfile
import unittest
from pathlib import Path

from studio.workflow import Studio
from studio.generators import prompt_for
from studio.intake import model_guidance


class ImageCompilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.studio = Studio(Path(self.temp.name)/'db', Path(self.temp.name)/'media', Path(self.temp.name)/'inbox')
        self.p = self.studio.create_project('Image compiler', 'image-poster', output_type='image')
        self.shot = self.p['shots'][0]
        self.shot['image_prompt'] = 'A hand-painted red boat'

    def test_edit_constraints_text_and_reference_roles_reach_actual_prompt(self):
        self.p = self.studio.update_shots(self.p['id'], [{'id': self.shot['id'], 'title': 'Poster', 'image_prompt': 'A hand-painted red boat', 'direction': {'image': {'mode': 'edit', 'instructions': 'Change the sail to yellow', 'preserve': 'Keep hull shape and brush texture', 'exact_text': ['Sail 2.1 — Today'], 'layout': 'Title in the upper third', 'background': 'Transparent background'}}}], self.p['revision'], 'user')
        self.shot = self.p['shots'][0]
        self.p['settings'].update(image_generator='qwen_image', image_model='Qwen-Image-2.1')
        self.p['assets'] = [{'id': 'ref', 'path': 'not-executed.png', 'kind': 'image', 'role': 'reference', 'name': 'Boat'}]
        self.shot['direction']['references'] = [{'slot': 'subject', 'asset_id': 'ref', 'role': 'prop', 'version': 1, 'entity_id': '', 'notes': 'Hull reference'}]
        result = prompt_for(self.p, self.shot, 'image')
        for text in ['Change the sail to yellow', 'Keep hull shape', 'Sail 2.1 — Today', 'upper third', 'Transparent background', 'subject', 'prop']:
            self.assertIn(text, result['prompt'])
        self.assertNotIn('No text', result['negative_prompt'])
        self.assertNotIn('No text', result['separate_notes']['avoid'])
        self.assertTrue(result['warnings'])
        self.assertEqual(result['model_guidance']['status'], 'documented')
        self.assertNotIn('Slow dolly', result['prompt'])
        self.assertNotIn('Cinematic realism', result['prompt'])
        self.assertNotIn('Warm amber', result['prompt'])
        self.assertNotIn('35mm', result['prompt'])

    def test_custom_template_is_not_rewritten_and_unknown_version_is_unverified(self):
        self.p['settings'].update(image_generator='custom', custom_image_template='{subject} --my-control 3.5', image_model='Private 9')
        result = prompt_for(self.p, self.shot, 'image')
        self.assertEqual(result['prompt'], 'A hand-painted red boat --my-control 3.5')
        self.assertEqual(model_guidance('qwen_image', 'Qwen-Image-99', 'image')['status'], 'custom_unverified')

    def test_edit_without_reference_warns_and_image_changes_invalidate_signature(self):
        before = self.studio._input_signature(self.p, self.shot, 'image')
        self.shot['direction']['image'] = {'mode': 'edit', 'instructions': 'Replace sky', 'preserve': 'Building', 'exact_text': [], 'layout': '', 'background': ''}
        result = prompt_for(self.p, self.shot, 'image')
        self.assertTrue(any('reference' in w.lower() for w in result['warnings']))
        self.assertNotEqual(before, self.studio._input_signature(self.p, self.shot, 'image'))

    def test_midjourney_parameters_remain_last_after_requirements(self):
        self.p['settings'].update(image_generator='midjourney_image', image_model='V7')
        self.shot['direction']['image'] = {'mode': 'generate', 'instructions': '', 'preserve': '', 'exact_text': ['HELLO'], 'layout': 'Centered', 'background': ''}
        result = prompt_for(self.p, self.shot, 'image')
        self.assertIn('HELLO', result['prompt'])
        self.assertTrue(result['prompt'].endswith('--ar ' + self.p['settings']['aspect_ratio']))

    def test_still_prompt_omits_voice_and_video_transition_instructions(self):
        self.p['production']['bible'] = [{'id':'hero','name':'Painter','identity':'Blue coat','wardrobe':'Apron','voice':'Deep booming voice','layout':'','light_sources':'','materials':''}]
        self.shot['direction']['action']['visible_entities'] = ['hero']
        self.shot['direction']['action']['transition'] = 'L-cut under the next video'
        result = prompt_for(self.p, self.shot, 'image')
        self.assertIn('Blue coat', result['prompt'])
        self.assertNotIn('booming voice', result['prompt'])
        self.assertNotIn('L-cut', result['prompt'])

    def test_qwen_edit_without_source_is_a_preflight_error(self):
        from studio.preflight import preflight
        self.shot['direction']['image'] = {'mode':'edit','instructions':'Replace sky','preserve':'','exact_text':[],'layout':'','background':''}
        result = preflight(self.p, self.shot['id'], 'image')
        self.assertTrue(any(i['rule']=='image_edit_reference' and i['severity']=='error' for i in result['issues']))
        self.p['assets'] = [{'id':'unrelated','kind':'image','role':'reference','path':'unrelated.png'}]
        self.assertTrue(any(i['rule']=='image_edit_reference' for i in preflight(self.p, self.shot['id'], 'image')['issues']))
        self.assertTrue(any('explicit' in w.lower() for w in prompt_for(self.p,self.shot,'image')['warnings']))

    def test_custom_image_requirements_are_visible_in_portable_markdown(self):
        p = self.studio.update_shots(self.p['id'], [{'id':self.shot['id'],'title':'Poster','image_prompt':'A boat','direction':{'image':{'exact_text':['SAIL TODAY'],'layout':'Upper third'}}}], self.p['revision'], 'user')
        p = self.studio.update_settings(p['id'], {'image_generator':'custom'}, p['revision'], 'user')
        result = self.studio.export_handoff(p['id'])
        self.assertIn('SAIL TODAY', result['markdown'])
        self.assertIn('Upper third', result['markdown'])


if __name__ == '__main__':
    unittest.main()
