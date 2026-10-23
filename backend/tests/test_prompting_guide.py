import tempfile
import unittest
from pathlib import Path

from studio.generators import IMAGE_PROFILES, prompt_for
from studio.workflow import Studio
from studio.prompting import prompting_guide, style_setups


class PromptingGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.studio = Studio(root/'data.db', root/'media', root/'inbox')
        self.project = self.studio.create_project('Study', 'custom')
        self.shot = self.project['shots'][0]
        self.shot.update(image_prompt='A ceramic bowl on a wooden table', motion_prompt='A hand turns the bowl gently')

    def test_subject_leads_image_and_purpose_is_not_lost(self):
        self.project['settings']['creative_intake'] = {'purpose': 'A craft catalogue'}
        result = prompt_for(self.project, self.shot, 'image')
        self.assertTrue(result['prompt'].startswith(self.shot['image_prompt']))
        self.assertIn('craft catalogue', result['separate_notes']['purpose'])

    def test_video_camera_leads_and_i2v_does_not_repaint_appearance(self):
        self.project['settings']['video_generator'] = 'runway_i2v'
        result = prompt_for(self.project, self.shot, 'video')
        self.assertTrue(result['prompt'].startswith('Camera movement:'))
        self.assertIn(self.shot['motion_prompt'], result['prompt'])
        self.assertNotIn(self.shot['image_prompt'], result['prompt'])

    def test_flux_and_midjourney_have_real_different_compilers(self):
        self.assertIn('flux_image', {p['id'] for p in IMAGE_PROFILES})
        self.project['settings'].update(image_generator='flux_image', image_model='FLUX.2', negative_prompt='blurred background')
        flux = prompt_for(self.project, self.shot, 'image')
        self.assertEqual(flux['negative_prompt'], '')
        self.assertEqual(flux['separate_notes']['avoid'], 'blurred background')
        self.assertNotIn('--ar', flux['prompt'])
        self.project['settings'].update(image_generator='midjourney_image', image_model='V7')
        mj = prompt_for(self.project, self.shot, 'image')
        self.assertTrue(mj['prompt'].endswith('--ar 16:9'))
        self.assertEqual(mj['model_guidance']['status'], 'documented')

    def test_shared_guide_is_attributed_with_corrections_and_safe_setups(self):
        guide = prompting_guide()
        self.assertIn('share.gemini.google', guide['source_url'])
        self.assertTrue(guide['corrections'])
        self.assertFalse(guide['guarantees_output'])
        self.assertEqual(len(style_setups()), 5)
        self.assertTrue(all(p['apply'] for p in style_setups()))


if __name__ == '__main__':
    unittest.main()
