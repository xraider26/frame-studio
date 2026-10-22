import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio.workflow import Studio
from studio.production import criteria_for
from studio.recipes import recipe_context
from studio.store import StudioError


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Real files require FFmpeg')
class RecipeTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.studio = Studio(root / 'db', root / 'media', root / 'inbox')
        self.p = self.studio.create_project('Synthetic software fixture, not artistic validation', 'ugc')
        self.source = root / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=orange:s=32x18:d=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(self.source)], check=True, capture_output=True)

    def prepared(self):
        def seed(p):
            p['settings']['aspect_ratio'] = '16:9'
            p['settings']['duration_seconds'] = 3
            p['production']['capabilities'].update(model='synthetic-test-model', confirmed=True, source='Software fixture only', observed_at='2026-10-22')
            for i, s in enumerate(p['shots']):
                s.update(duration_seconds=1, edit_duration_seconds=1)
                key = f'video-{i}'
                dest = self.studio.media_root / (key + '.mp4')
                shutil.copyfile(self.source, dest)
                p['assets'].append({'id': key, 'kind': 'video', 'shot_id': s['id'], 'path': str(dest), 'stale': False,
                    'input_signature': self.studio._input_signature(p, s, 'video'),
                    'review': {'criteria': {c: True for c in criteria_for(p, s, 'video')}, 'inspected': ['beginning', 'middle', 'end'], 'defect': '', 'actor': 'agent:fixture'}})
                s['video_asset'] = key
            dest = self.studio.media_root / 'final.mp4'
            shutil.copyfile(self.source, dest)
            p['assets'].append({'id': 'final', 'kind': 'final_video', 'path': str(dest), 'stale': False})
            p['documents']['final_review'] = {'export_asset_id': 'final', 'text': 'Synthetic export'}
        return self.studio.mutate(self.p['id'], self.p['revision'], seed)

    def assessment(self, p):
        return {'asset_id': 'final', 'inspected': ['beginning', 'middle', 'end'], 'watched_full': True,
                'criteria': {c: True for c in recipe_context(p)['final_checks']},
                'note': 'Synthetic file used to test evidence handling; no artistic validation.', 'defects': '', 'idea': 'Synthetic cup example'}

    def test_requires_real_final_video_human_actor_scope_and_full_recorded_review(self):
        self.assertTrue(hasattr(self.studio, 'record_recipe_trial'))
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(self.p['id'], self.assessment(self.p), self.p['revision'], 'user')
        p = self.prepared()
        for actor, change in [('agent:test', {}), ('user', {'watched_full': False}), ('user', {'criteria': {}}), ('user', {'asset_id': 'video-0'})]:
            with self.subTest(actor=actor, change=change), self.assertRaises(StudioError):
                self.studio.record_recipe_trial(p['id'], {**self.assessment(p), **change}, p['revision'], actor)
        result = self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')
        self.assertEqual(len(result['trials']), 1)
        trial = result['trials'][0]
        self.assertTrue(trial['passed'])
        self.assertEqual(trial['model_scope']['capabilities']['model'], 'synthetic-test-model')
        self.assertEqual(len(trial['shot_evidence']), 3)
        self.assertTrue(trial['final_file']['sha256'])
        self.assertTrue(trial['matches_current_inputs'])
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')

    def test_changed_inputs_do_not_inherit_pass_and_repeated_click_is_not_another_trial(self):
        self.assertTrue(hasattr(self.studio, 'record_recipe_trial'))
        p = self.prepared()
        self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')
        p = self.studio.get_project(p['id'])
        self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')
        self.assertEqual(len(self.studio.recipe_trials(p['id'])['trials']), 1)
        p = self.studio.get_project(p['id'])
        p = self.studio.mutate(p['id'], p['revision'], lambda q: q['settings'].update(lens='Custom lens'))
        self.assertFalse(self.studio.recipe_trials(p['id'])['trials'][0]['matches_current_inputs'])

    def test_missing_file_unverified_model_and_failed_shot_cannot_be_called_passed(self):
        self.assertTrue(hasattr(self.studio, 'record_recipe_trial'))
        p = self.prepared()
        p = self.studio.mutate(p['id'], p['revision'], lambda q: q['production']['capabilities'].update(confirmed=False))
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')

    def test_malformed_inspection_returns_a_structured_validation_error(self):
        p = self.prepared()
        assessment = self.assessment(p)
        assessment['inspected'].append({})
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(p['id'], assessment, p['revision'], 'user')

    def test_actual_selected_clip_must_cover_the_retained_source_range(self):
        p = self.prepared()
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=32x18:d=0.1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(self.studio.media_root / 'video-0.mp4')], check=True, capture_output=True)
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')

    def test_missing_selected_source_file_does_not_match_current_evidence(self):
        p = self.prepared()
        self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')
        (self.studio.media_root / 'video-0.mp4').unlink()
        self.assertFalse(self.studio.recipe_trials(p['id'])['trials'][0]['matches_current_inputs'])

    def test_defective_selected_take_and_missing_final_are_rejected(self):
        p = self.prepared()
        p = self.studio.mutate(p['id'], p['revision'], lambda q: q['assets'][0]['review'].update(defect='Broken hand'))
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')
        p = self.studio.mutate(p['id'], p['revision'], lambda q: q['assets'][0]['review'].update(defect=''))
        (self.studio.media_root / 'final.mp4').unlink()
        with self.assertRaises(StudioError):
            self.studio.record_recipe_trial(p['id'], self.assessment(p), p['revision'], 'user')
