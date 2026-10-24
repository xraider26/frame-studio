from workflow_fixtures import CREATOR_SETTINGS, creator_ready
import base64
import tempfile
import unittest
import shutil
import subprocess
import json
import zipfile
from pathlib import Path

from PIL import Image

try:
    from studio.workflow import Studio, StudioError
except ImportError:
    Studio = None
    StudioError = ValueError


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Studio, 'Shared studio workflow is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.inbox = root / 'inbox'
        self.inbox.mkdir()
        self.studio = Studio(root / 'workflow.db', root / 'media', self.inbox)
        self.project = self.studio.create_project('A small film', 'ai-film')
        self.project = creator_ready(self.studio, self.project)
        self.project = self.studio.set_policy(self.project['id'], {s: True for s in self.project['approval_policy']}, self.project['revision'])
        # Exercise the original optional-QC workflow; course contracts have separate tests.
        self.project = self.studio.update_production(self.project['id'], {'recipe': {}, 'require_recorded_checks': False}, self.project['revision'], 'user')

    def complete(self, step, output):
        p = self.studio.get_project(self.project['id'])
        self.project = self.studio.complete_step(p['id'], step, output, p['revision'], 'test-agent')
        return self.project

    def prepare(self):
        p = self.project
        self.project = self.studio.set_policy(p['id'], {'brief': False, 'script': False}, p['revision'])
        self.complete('brief', {'text': 'A traveler finds an abandoned observatory.'})
        self.complete('script', {'text': 'She enters. The stars begin to move.'})
        p = self.project
        self.project = self.studio.update_shots(p['id'], [{'title': 'Arrival', 'image_prompt': 'Traveler by observatory', 'motion_prompt': 'Slow dolly toward doorway'}], p['revision'], 'test-agent')

    def image(self, name='frame.png'):
        path = self.inbox / name
        Image.new('RGB', (32, 18), '#ff8833').save(path)
        return path

    def test_manual_review_blocks_and_auto_policy_progresses(self):
        p = self.complete('brief', {'text': 'Useful creative brief'})
        self.assertEqual(self.studio.next_action(p['id'])['action'], 'await_approval')
        with self.assertRaises(StudioError):
            self.complete('script', {'text': 'Cannot bypass brief'})
        p = self.studio.set_policy(p['id'], {'brief': False}, p['revision'])
        self.assertEqual(p['steps']['brief']['status'], 'auto_proceeded')
        self.assertEqual(self.studio.next_action(p['id'])['step'], 'script')
        self.assertFalse(any(e['type'] == 'human_approved' for e in p['history']))

    def test_real_result_matches_handoff_and_duplicate_is_idempotent(self):
        self.prepare()
        task = self.studio.claim_next(self.project['id'], 'cursor', 'task-1')
        same = self.studio.claim_next(self.project['id'], 'claude', 'task-2')
        self.assertEqual(task['job']['id'], same['job']['id'])
        self.assertEqual(task['handoff']['kind'], 'image')
        result = self.studio.return_result(task['job']['id'], str(self.image()), 'cursor')
        duplicate = self.studio.return_result(task['job']['id'], str(self.image()), 'cursor')
        self.assertEqual(result['asset']['id'], duplicate['asset']['id'])
        self.assertEqual(len(self.studio.get_project(self.project['id'])['assets']), 1)
        self.assertEqual(self.studio.next_action(self.project['id'])['action'], 'await_approval')

    def test_auto_visual_step_advances_to_pilot(self):
        self.prepare()
        p = self.project
        self.studio.set_policy(p['id'], {'visual_direction': False}, p['revision'])
        task = self.studio.claim_next(p['id'], 'codex', 'one')
        self.studio.return_result(task['job']['id'], str(self.image()), 'codex')
        action = self.studio.next_action(p['id'])
        self.assertEqual((action['step'], action['kind']), ('pilot', 'video'))

    def test_late_result_after_prompt_change_is_retained_without_advancing(self):
        self.prepare()
        task = self.studio.claim_next(self.project['id'], 'agent', 'one')
        p = self.studio.get_project(self.project['id'])
        shots = [dict(p['shots'][0], image_prompt='Completely different direction')]
        self.studio.update_shots(p['id'], shots, p['revision'], 'agent')
        returned = self.studio.return_result(task['job']['id'], str(self.image()), 'agent')
        self.assertTrue(returned['asset']['stale'])
        p = self.studio.get_project(p['id'])
        self.assertIsNone(p['shots'][0]['image_asset'])
        self.assertEqual(self.studio.next_action(p['id'])['kind'], 'image')

    def test_revision_conflict_has_no_side_effect(self):
        p = self.complete('brief', {'text': 'Brief'})
        with self.assertRaises(StudioError):
            self.studio.set_policy(p['id'], {'brief': False}, 1)
        self.assertTrue(self.studio.get_project(p['id'])['approval_policy']['brief'])

    def test_turning_review_back_on_requires_human_decision(self):
        p = self.project
        p = self.studio.set_policy(p['id'], {'brief': False}, p['revision'])
        self.complete('brief', {'text': 'Brief'})
        p = self.studio.get_project(p['id'])
        p = self.studio.set_policy(p['id'], {'brief': True}, p['revision'])
        self.assertEqual(self.studio.next_action(p['id'])['action'], 'await_approval')
        p = self.studio.review(p['id'], 'brief', True, 'Looks good', p['revision'])
        self.assertEqual(p['steps']['brief']['status'], 'approved')

    def test_outside_inbox_and_invalid_image_rejected(self):
        self.prepare()
        task = self.studio.claim_next(self.project['id'], 'agent', 'one')
        outside = Path(self.temp.name) / 'outside.png'
        Image.new('RGB', (8, 8)).save(outside)
        with self.assertRaises(StudioError):
            self.studio.return_result(task['job']['id'], str(outside), 'agent')
        invalid = self.inbox / 'fake.png'
        invalid.write_text('not an image')
        with self.assertRaises(StudioError):
            self.studio.return_result(task['job']['id'], str(invalid), 'agent')
        self.assertEqual(len(self.studio.get_project(self.project['id'])['assets']), 0)

    def test_projects_are_isolated_and_state_survives_restart(self):
        self.complete('brief', {'text': 'Saved'})
        second = self.studio.create_project('Another project', 'ugc')
        self.assertFalse(second['steps']['brief']['ready'])
        reopened = Studio(self.studio.db_path, self.studio.media_root, self.inbox)
        self.assertEqual(reopened.get_project(self.project['id'])['documents']['brief']['text'], 'Saved')

    def test_config_change_reopens_downstream_work(self):
        self.prepare()
        p = self.studio.get_project(self.project['id'])
        p = self.studio.update_settings(p['id'], {'lighting': 'Blue hour'}, p['revision'], 'agent')
        self.assertEqual(p['settings']['lighting'], 'Blue hour')
        self.assertEqual(p['steps']['brief']['status'], 'auto_proceeded')
        self.assertEqual(p['steps']['visual_direction']['status'], 'draft')

    def test_retry_claim_after_result_returns_original_job(self):
        self.prepare()
        p = self.project
        self.studio.set_policy(p['id'], {'visual_direction': False}, p['revision'])
        task = self.studio.claim_next(p['id'], 'agent', 'stable-request')
        self.studio.return_result(task['job']['id'], str(self.image()), 'agent')
        retried = self.studio.claim_next(p['id'], 'agent', 'stable-request')
        self.assertEqual(retried['job']['id'], task['job']['id'])
        self.assertTrue(retried['already_claimed'])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required for real MP4 validation')
    def test_rejected_pilot_requires_a_new_video_take(self):
        self.prepare()
        p = self.project
        self.studio.set_policy(p['id'], {'visual_direction': False}, p['revision'])
        image_job = self.studio.claim_next(p['id'], 'agent', 'image')
        self.studio.return_result(image_job['job']['id'], str(self.image()), 'agent')
        video_job = self.studio.claim_next(p['id'], 'agent', 'video')
        video = self.inbox / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=orange:s=64x36:d=0.5', '-pix_fmt', 'yuv420p', str(video)], check=True, capture_output=True)
        self.studio.return_result(video_job['job']['id'], str(video), 'agent')
        p = self.studio.get_project(p['id'])
        self.studio.review(p['id'], 'pilot', False, 'Change the camera motion', p['revision'])
        action = self.studio.next_action(p['id'])
        self.assertEqual((action['action'], action['step']), ('generate', 'pilot'))
        new_job = self.studio.claim_next(p['id'], 'agent', 'new-video')
        self.assertNotEqual(video_job['job']['id'], new_job['job']['id'])

    def test_generator_profile_changes_exported_prompts_and_zip_is_portable(self):
        self.prepare()
        p = self.studio.get_project(self.project['id'])
        p = self.studio.update_settings(p['id'], {'video_generator': 'flow_veo'}, p['revision'], 'agent')
        flow = self.studio.export_handoff(p['id'])
        p = self.studio.update_settings(p['id'], {'video_generator': 'runway_i2v'}, p['revision'], 'agent')
        runway = self.studio.export_handoff(p['id'])
        self.assertNotEqual(flow['manifest']['shots'][0]['video']['prompt'], runway['manifest']['shots'][0]['video']['prompt'])
        with zipfile.ZipFile(runway['path']) as archive:
            self.assertIn('manifest.json', archive.namelist())
            self.assertIn('prompts.md', archive.namelist())
            data = json.loads(archive.read('manifest.json'))
            self.assertEqual(data['video_generator'], 'runway_i2v')
            self.assertNotIn(str(self.studio.media_root), archive.read('manifest.json').decode())

    def test_duplicate_keeps_plan_but_resets_outputs_and_approval(self):
        self.prepare()
        clone = self.studio.duplicate_project(self.project['id'], 'Alternate cut', 'agent')
        self.assertNotEqual(clone['id'], self.project['id'])
        self.assertEqual(clone['documents']['script']['text'], 'She enters. The stars begin to move.')
        self.assertNotEqual(clone['shots'][0]['id'], self.project['shots'][0]['id'])
        self.assertEqual(clone['jobs'], [])
        self.assertEqual(clone['steps']['brief']['status'], 'auto_proceeded')

    def test_delete_is_recoverable_and_hidden_from_agents(self):
        p = self.project
        self.studio.delete_project(p['id'], p['revision'])
        self.assertEqual(self.studio.list_projects(), [])
        self.assertEqual(len(self.studio.list_deleted()), 1)
        with self.assertRaises(StudioError):
            self.studio.claim_next(p['id'], 'agent', 'should-not-run')
        self.studio.restore_project(p['id'])
        self.assertEqual(len(self.studio.list_projects()), 1)

    def test_provider_failure_cannot_replace_an_already_returned_result(self):
        from studio.providers import Providers
        self.prepare()
        task = self.studio.claim_next(self.project['id'], 'agent', 'one')
        self.studio.return_result(task['job']['id'], str(self.image()), 'agent')
        Providers(self.studio, Path(self.temp.name) / 'connections.json')._failed(task['job']['id'], 'failed', 'late provider timeout')
        self.assertEqual(self.studio.find_job(task['job']['id'])[1]['status'], 'succeeded')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_rejected_pilot_invalidates_inflight_production_take(self):
        self.prepare()
        p = self.project
        p = self.studio.set_policy(p['id'], {'visual_direction': False, 'pilot': False}, p['revision'])
        self.studio.update_shots(p['id'], [{'title': 'One', 'image_prompt': 'One', 'motion_prompt': 'Move'}, {'title': 'Two', 'image_prompt': 'Two', 'motion_prompt': 'Move'}], p['revision'], 'agent')
        for i in range(2):
            j = self.studio.claim_next(p['id'], 'agent', 'image-' + str(i))
            self.studio.return_result(j['job']['id'], str(self.image()), 'agent')
        video = self.inbox / 'video.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=orange:s=64x36:d=0.5', '-pix_fmt', 'yuv420p', str(video)], check=True, capture_output=True)
        pilot = self.studio.claim_next(p['id'], 'agent', 'pilot')
        self.studio.return_result(pilot['job']['id'], str(video), 'agent')
        pending = self.studio.claim_next(p['id'], 'agent', 'production')
        p = self.studio.get_project(p['id'])
        p = self.studio.set_policy(p['id'], {'pilot': True}, p['revision'])
        self.studio.review(p['id'], 'pilot', False, 'Different motion', p['revision'])
        result = self.studio.return_result(pending['job']['id'], str(video), 'agent')
        self.assertTrue(result['asset']['stale'])
        p = self.studio.get_project(p['id'])
        self.assertIsNone(p['shots'][1]['video_asset'])

    def test_api_start_honors_a_newly_enabled_earlier_review_gate(self):
        import asyncio
        from studio.providers import Providers
        self.prepare()
        job = self.studio.claim_next(self.project['id'], 'agent', 'queued-image')
        p = self.studio.get_project(self.project['id'])
        self.studio.set_policy(p['id'], {'script': True}, p['revision'])
        provider = Providers(self.studio, Path(self.temp.name) / 'connections.json')
        provider.save({'id': 'local', 'name': 'Local fixture', 'base_url': 'http://127.0.0.1:9', 'enabled': True, 'max_requests': 1})
        async def submit():
            with self.assertRaises(StudioError):
                provider.submit(job['job']['id'], 'local')
        asyncio.run(submit())
        self.assertEqual(provider.public()[0]['used_requests'], 0)


if __name__ == '__main__':
    unittest.main()
