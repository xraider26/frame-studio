from workflow_fixtures import CREATOR_SETTINGS
import base64
import io
import json
import tempfile
import unittest
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient

try:
    from studio.api import create_app
    from studio.providers import decode_output
except ImportError:
    create_app = None
    decode_output = None


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(create_app, 'Studio API is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(Path(self.temp.name), 'agent-test', 'browser-test')
        self.client = TestClient(self.app)
        self.agent = {'Authorization': 'Bearer agent-test'}
        self.browser = {'Authorization': 'Bearer browser-test'}

    def command(self, op, args=None, headers=None):
        return self.client.post('/studio/v1/command', json={'operation': op, 'arguments': args or {}, 'actor': 'test'}, headers=headers or self.agent)

    def test_agent_cannot_change_user_review_policy_or_approve(self):
        p = self.command('create_project', {'name': 'Test', 'template_id': 'ugc'}).json()
        args = {'project_id': p['id'], 'policy': {'brief': False}, 'expected_revision': p['revision']}
        self.assertEqual(self.command('set_policy', args).status_code, 403)
        self.assertEqual(self.command('set_policy', args, self.browser).status_code, 200)
        self.assertEqual(self.command('review', {}).status_code, 403)

    def test_authentication_and_unknown_operations_fail(self):
        res = self.client.post('/studio/v1/command', json={'operation': 'list_projects'})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self.command('run_shell', {'command': 'anything'}).status_code, 400)

    def test_unconfigured_provider_does_not_start_fake_generation(self):
        result = self.command('studio_capabilities').json()
        self.assertEqual(result['connections'], [])
        self.assertEqual(result['flow_account'], 'not_connected')

    def test_connection_secrets_never_echoed_or_available_to_agent(self):
        data = {'id': 'test-api', 'name': 'My local API', 'base_url': 'http://127.0.0.1:8999', 'api_key': 'secret-not-for-output', 'enabled': False, 'max_requests': 2}
        res = self.command('save_connection', data, self.browser)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertNotIn('secret-not-for-output', res.text)
        self.assertNotIn('secret-not-for-output', self.command('studio_capabilities').text)
        self.assertEqual(self.command('save_connection', data).status_code, 403)

    def test_provider_output_is_real_media_not_success_text(self):
        self.assertIsNotNone(decode_output)
        with self.assertRaises(ValueError):
            decode_output({'status': 'succeeded', 'output': {'url': 'https://example.com/fake.png'}}, 'image')
        buf = io.BytesIO()
        Image.new('RGB', (8, 8), 'orange').save(buf, format='PNG')
        content, suffix = decode_output({'status': 'succeeded', 'output': {'base64': base64.b64encode(buf.getvalue()).decode(), 'mime_type': 'image/png'}}, 'image')
        self.assertTrue(content.startswith(b'\x89PNG'))
        self.assertEqual(suffix, '.png')

    def test_configured_api_generator_roundtrip_attaches_real_output(self):
        self.assertIsNotNone(create_app)
        buf = io.BytesIO()
        Image.new('RGB', (16, 9), 'orange').save(buf, format='PNG')
        encoded = base64.b64encode(buf.getvalue()).decode()
        class Generator(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(200 if payload.get('prompt') else 400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'succeeded', 'output': {'base64': encoded, 'mime_type': 'image/png'}}).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Generator)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with TestClient(self.app) as client:
            self.client = client
            p = self.command('create_project', {'name': 'API connector fixture', 'template_id': 'ai-film', 'settings': CREATOR_SETTINGS}).json()
            p = self.command('set_policy', {'project_id': p['id'], 'policy': {'brief': False, 'script': False, 'visual_direction': False}, 'expected_revision': p['revision']}, self.browser).json()
            p = self.command('update_production', {'project_id': p['id'], 'production': {'require_recorded_checks': False}, 'expected_revision': p['revision']}, self.browser).json()
            for step in ['brief', 'script']:
                p = self.command('complete_step', {'project_id': p['id'], 'step': step, 'output': {'text': 'Actual test document'}, 'expected_revision': p['revision']}).json()
            p = self.command('update_shots', {'project_id': p['id'], 'shots': [{'title': 'Test', 'image_prompt': 'Fixture image', 'motion_prompt': 'Slow motion'}], 'expected_revision': p['revision']}).json()
            job = self.command('claim_generation', {'project_id': p['id'], 'request_id': 'api-image'}).json()['job']
            self.command('save_connection', {'id': 'local-test', 'name': 'Local contract fixture', 'base_url': f'http://127.0.0.1:{server.server_port}', 'enabled': True, 'max_requests': 1}, self.browser)
            res = self.command('run_provider', {'job_id': job['id'], 'connection_id': 'local-test'})
            self.assertEqual(res.status_code, 200, res.text)
            for _ in range(50):
                current = self.command('get_job', {'job_id': job['id']}).json()
                if current['status'] != 'running':
                    break
                time.sleep(.05)
            self.assertEqual(current['status'], 'succeeded', current)
            p = self.command('get_project', {'project_id': p['id']}).json()
            self.assertEqual(p['next_action']['step'], 'pilot')
            self.assertEqual(len(p['assets']), 1)
            self.assertTrue(Path(p['assets'][0]['path']).is_file())


if __name__ == '__main__':
    unittest.main()
