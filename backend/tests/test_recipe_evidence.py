import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio.production import criteria_for
from studio.store import StudioError
from studio.workflow import Studio


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Real media validation requires FFmpeg')
class RecipeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.studio = Studio(root / 'db', root / 'media', root / 'inbox')
        self.p = self.studio.create_project('Observed pilot', 'ai-film')
        self.video = root / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=orange:s=32x18:d=0.1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(self.video)], capture_output=True, check=True)

    def capture(self, sections=None, settings_shot_id=''):
        return self.studio.save_project_template(self.p['id'], 'Observed recipe', '', sections or ['settings', 'workflow', 'story'], self.p['revision'], settings_shot_id)

    def videos(self, p, all_shots=False):
        def seed(current):
            for i, shot in enumerate(current['shots'] if all_shots else current['shots'][:1]):
                key = 'video-' + str(i)
                dest = self.studio.media_root / (current['id'] + key + '.mp4')
                shutil.copyfile(self.video, dest)
                review = {'criteria': {c: True for c in criteria_for(current, shot, 'video')}, 'inspected': ['beginning', 'middle', 'end'], 'defect': '', 'notes': 'Synthetic fixture inspected for software verification', 'actor': 'agent', 'at': '2026-10-22T00:00:00+00:00'}
                current['assets'].append({'id': key, 'kind': 'video', 'shot_id': shot['id'], 'path': str(dest), 'stale': False, 'input_signature': self.studio._input_signature(current, shot, 'video'), 'review': review, 'review_history': [copy.deepcopy(review)]})
                shot['video_asset'] = key
        return self.studio.mutate(p['id'], p['revision'], seed)

    def endorse(self, saved, p=None, level='pilot'):
        self.assertTrue(hasattr(self.studio, 'endorse_recipe'), 'Missing evidence-backed recipe endorsement')
        p = p or self.p
        return self.studio.endorse_recipe(saved['id'], p['id'], 'Human inspected the fixture; software test only', p['revision'], saved['revision'], level)

    def test_source_and_copy_usage_are_traceable_without_a_quality_claim(self):
        saved = self.capture()
        template = self.studio.get_saved_template(saved['id'])
        self.assertEqual(template.get('source_project_id'), self.p['id'])
        self.assertEqual(template.get('source_project_revision'), self.p['revision'])
        self.assertTrue(template.get('snapshot_hash'))
        clone = self.studio.create_project('Copy', saved['id'])
        self.assertEqual(clone['template_source'].get('snapshot_hash'), template['snapshot_hash'])
        metrics = self.studio.recipe_metrics(saved['id'])
        self.assertEqual(metrics['usage_count'], 1)
        self.assertEqual(metrics['evidence'], [])
        self.assertEqual({p['id'] for p in metrics['projects']}, {clone['id'], self.p['id']})

    def test_pilot_records_human_attribution_review_and_historical_scope(self):
        saved = self.capture()
        self.p = self.videos(self.p)
        result = self.endorse(saved)
        evidence = result['evidence'][0]
        self.assertEqual(evidence['level'], 'pilot')
        self.assertEqual(evidence['actor'], 'user')
        self.assertEqual(evidence['project_revision'], self.p['revision'])
        self.assertEqual(evidence['assets'][0]['id'], 'video-0')
        self.assertEqual(evidence['assets'][0]['review']['inspected'], ['beginning', 'middle', 'end'])
        self.assertIn('historical', result['scope'].lower())
        self.assertEqual(result['template_revision'], saved['revision'] + 1)
        with self.assertRaises(StudioError):
            self.endorse(saved)

    def test_absent_video_cannot_endorse_a_configuration(self):
        self.endorse_rejected(self.capture(), self.p)

    def endorse_rejected(self, saved, p):
        self.assertTrue(hasattr(self.studio, 'endorse_recipe'), 'Missing evidence-backed recipe endorsement')
        with self.assertRaises(StudioError):
            self.endorse(saved, p)

    def test_missing_stale_incompatible_defective_and_incomplete_media_are_rejected(self):
        saved = self.capture()
        self.p = self.videos(self.p)
        original = copy.deepcopy(self.p)
        mutations = [lambda a: a.update(stale=True), lambda a: a.update(path=str(self.video.parent/'missing.mp4')), lambda a: a.update(input_signature='changed'), lambda a: a['review'].update(defect='Fused hand'), lambda a: a['review'].update(inspected=['beginning']), lambda a: a['review'].update(criteria={})]
        for change in mutations:
            with self.subTest(change=change):
                def alter(p):
                    p['assets'] = copy.deepcopy(original['assets'])
                    change(p['assets'][0])
                self.p = self.studio.mutate(self.p['id'], self.p['revision'], alter)
                self.endorse_rejected(saved, self.p)

    def test_changed_settings_cannot_inherit_evidence_even_with_compatible_new_output(self):
        saved = self.capture()
        self.p = self.studio.update_settings(self.p['id'], {'lens': '135mm'}, self.p['revision'], 'user')
        self.p = self.videos(self.p)
        self.endorse_rejected(saved, self.p)

    def test_clone_shot_ids_are_remapped_but_story_edits_do_not_match(self):
        saved = self.capture()
        clone = self.studio.create_project('Copy', saved['id'])
        clone = self.videos(clone)
        result = self.endorse(saved, clone)
        self.assertEqual(result['evidence'][0]['project_id'], clone['id'])
        saved['revision'] = result['template_revision']
        shots = copy.deepcopy(clone['shots'])
        shots[0]['motion_prompt'] = 'New incompatible story'
        clone = self.studio.update_shots(clone['id'], shots, clone['revision'], 'agent')
        clone = self.videos(clone)
        self.endorse_rejected(saved, clone)

    def test_production_requires_every_shot_and_effective_criteria(self):
        saved = self.capture()
        self.p = self.videos(self.p)
        with self.assertRaises(StudioError):
            self.endorse(saved, level='production')
        self.p = self.videos(self.p, all_shots=True)
        result = self.endorse(saved, level='production')
        self.assertEqual(len(result['evidence'][0]['assets']), len(self.p['shots']))

    def test_source_shot_look_must_still_match_and_be_inspected(self):
        shots = copy.deepcopy(self.p['shots'])
        shots[1]['direction']['camera']['lens'] = '135mm portrait'
        self.p = self.studio.update_shots(self.p['id'], shots, self.p['revision'], 'user')
        saved = self.capture(['settings'], self.p['shots'][1]['id'])
        self.p = self.videos(self.p)
        self.endorse_rejected(saved, self.p)
        self.p = self.videos(self.p, all_shots=True)
        self.assertEqual(len(self.endorse(saved)['evidence'][0]['assets']), 2)

    def test_settings_recipe_cannot_be_endorsed_using_a_different_effective_shot_look(self):
        saved = self.capture(['settings'])
        shots = copy.deepcopy(self.p['shots'])
        shots[0]['direction']['camera']['lens'] = '135mm override bypasses defaults'
        self.p = self.studio.update_shots(self.p['id'], shots, self.p['revision'], 'user')
        self.p = self.videos(self.p)
        self.endorse_rejected(saved, self.p)

    def test_costs_remain_grouped_and_unknowns_are_visible(self):
        saved = self.capture(['settings'])
        self.assertTrue(hasattr(self.studio, 'recipe_metrics'), 'Missing recipe usage metrics')
        clone = self.studio.create_project('Copy', saved['id'])
        self.studio.mutate(self.p['id'], self.p['revision'], lambda p: p['jobs'].extend([{'id': 'one', 'cost': {'unit': 'USD', 'actual': 3, 'planned': 2}}, {'id': 'two', 'cost': {'unit': 'USD', 'planned': 4}}]))
        self.studio.mutate(clone['id'], clone['revision'], lambda p: p['jobs'].extend([{'id': 'three', 'cost': {'unit': 'credits', 'actual': 8}}, {'id': 'four', 'cost': {'unit': 'credits'}}]))
        costs = {c['unit']: c for c in self.studio.recipe_metrics(saved['id'])['costs']}
        self.assertEqual(costs['USD']['reported_actual'], 3)
        self.assertEqual(costs['USD']['planned_unsettled'], 4)
        self.assertEqual(costs['USD']['unknown_actual_jobs'], 1)
        self.assertEqual(costs['credits']['reported_actual'], 8)
        self.assertEqual(costs['credits']['unknown_exposure_jobs'], 1)

    def test_legacy_templates_remain_usable_without_evidence(self):
        saved = self.capture()
        with self.studio.connect() as conn:
            t = self.studio.get_saved_template(saved['id'])
            for key in ['source_project_id', 'source_project_revision', 'snapshot_hash', 'settings_shot_id']:
                t.pop(key, None)
            conn.execute('UPDATE studio_templates SET payload=? WHERE id=?', (json.dumps(t), t['id']))
        self.assertTrue(self.studio.create_project('Legacy copy', saved['id'])['id'])
        self.assertEqual(self.studio.recipe_metrics(saved['id'])['evidence'], [])
