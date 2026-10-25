import io
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from studio.api import create_app
from test_comfy_connector import config
from workflow_fixtures import CREATOR_SETTINGS


class ComfyProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.app = create_app(Path(self.temp.name), 'agent', 'browser')
        self.client = TestClient(self.app)

    def command(self, op, args=None, human=True):
        return self.client.post('/studio/v1/command', headers={'Authorization': 'Bearer ' + ('browser' if human else 'agent')}, json={'operation': op, 'arguments': args or {}})

    def test_comfy_config_validated_and_legacy_connection_defaults_survive(self):
        data = {'id': 'comfy', 'base_url': 'http://127.0.0.1:8188', 'adapter': 'comfyui', 'comfy': config(), 'enabled': True}
        response = self.command('save_connection', data)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]['adapter'], 'comfyui')
        self.assertEqual(response.json()[0]['comfy']['workflow']['22']['inputs']['steps'], 8)
        self.assertEqual(self.command('save_connection', {**data, 'comfy': {'kind': 'image'}}).status_code, 400)
        self.assertEqual(self.command('save_connection', data, human=False).status_code, 403)
        self.assertEqual(self.command('save_connection', {'id': 'legacy', 'base_url': 'http://127.0.0.1:9000'}).status_code, 200)

    def test_roundtrip_attaches_validated_image_and_remote_prompt_id(self):
        self.roundtrip()

    def test_connection_disabled_during_preflight_never_submits_remote_prompt(self):
        self.roundtrip(disable=True)

    def roundtrip(self, disable=False):
        buf = io.BytesIO(); Image.new('RGB', (16, 9), 'blue').save(buf, format='PNG')
        content = buf.getvalue(); submitted = []; schema_reads=[]; owner=self
        schema = {n['class_type']: {'output_node': n['class_type'] == 'Save', 'input': {'required': {k: ['STRING'] for k in n['inputs']}}} for n in config()['workflow'].values()}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/object_info':
                    schema_reads.append(1)
                    if disable and len(schema_reads)>1:
                        owner.app.state.providers.connections['comfy']['enabled']=False
                    data = schema
                elif self.path.startswith('/history/'): data = {'remote-123': {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'33': {'images': [{'filename': 'result.png', 'type': 'output'}]}}}}
                else:
                    self.send_response(200); self.end_headers(); self.wfile.write(content); return
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(data).encode())
            def do_POST(self):
                submitted.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"prompt_id":"remote-123"}')
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with TestClient(self.app) as client:
            self.client = client
            p = self.command('create_project', {'name': 'Comfy fixture', 'template_id': 'image-custom', 'output_type': 'image', 'settings': CREATOR_SETTINGS}).json()
            for step in ['brief', 'script']:
                p = self.command('complete_step', {'project_id': p['id'], 'step': step, 'output': {'text': 'Fixture direction'}, 'expected_revision': p['revision']}).json()
            p = self.command('update_shots', {'project_id': p['id'], 'shots': [{'id': p['shots'][0]['id'], 'title': 'Boat', 'image_prompt': 'A blue boat'}], 'expected_revision': p['revision']}).json()
            claimed = self.command('claim_generation', {'project_id': p['id'], 'request_id': 'comfy-image', 'expected_revision': p['revision']}).json()
            job = claimed['job']
            self.assertIsNotNone(job, claimed)
            conn = {'id': 'comfy', 'base_url': f'http://127.0.0.1:{server.server_port}', 'adapter': 'comfyui', 'comfy': config(), 'enabled': True}
            self.assertEqual(self.command('save_connection', conn).status_code, 200)
            self.assertEqual(self.command('validate_connection', {'connection_id': 'comfy'}).status_code, 200)
            response = self.command('run_provider', {'job_id': job['id'], 'connection_id': 'comfy'})
            self.assertEqual(response.status_code, 200, response.text)
            for _ in range(80):
                current = self.command('get_job', {'job_id': job['id']}).json()
                if current['status'] != 'running': break
                time.sleep(.025)
            if disable:
                self.assertEqual(current['status'],'failed',current)
                self.assertEqual(submitted,[])
                return
            self.assertEqual(current['status'], 'succeeded', current)
            current = self.command('get_job', {'job_id': job['id'], 'detail': 'full'}).json()
            self.assertEqual(current['remote_prompt_id'], 'remote-123')
            self.assertEqual(current['execution']['evidence_source'], 'server_recorded')
            self.assertEqual(current['execution']['validation']['state'], 'match')
            self.assertEqual(current['execution']['arguments']['prompt'], submitted[0]['prompt'])
            self.assertEqual(current['execution']['prompt'], submitted[0]['prompt']['11']['inputs']['text'])
            self.assertEqual(submitted[0]['prompt']['22']['inputs']['steps'], 8)
            project = self.command('get_project', {'project_id': p['id']}).json()
            self.assertTrue(Path(project['assets'][0]['path']).is_file())
            self.assertEqual(project['assets'][0]['mime'], 'image/png')
            self.assertEqual(self.command('run_provider', {'job_id': job['id'], 'connection_id': 'comfy'}).status_code, 409)

    def test_portable_export_contains_workflow_and_no_connection_key(self):
        p = self.command('create_project', {'name': 'Portable', 'template_id': 'image-custom', 'output_type': 'image'}).json()
        self.command('save_connection', {'id': 'comfy', 'base_url': 'http://localhost:8188', 'api_key': 'private-key', 'adapter': 'comfyui', 'comfy': config()})
        response = self.command('export_comfy_handoff', {'project_id': p['id'], 'connection_id': 'comfy'})
        self.assertEqual(response.status_code, 200, response.text)
        import zipfile
        with zipfile.ZipFile(response.json()['path']) as archive:
            self.assertTrue(any(n.startswith('workflows/') for n in archive.namelist()))
            self.assertNotIn(b'private-key', b''.join(archive.read(n) for n in archive.namelist()))

    def test_raw_configuration_roundtrips_full_uint64_seed(self):
        c = config(); c['workflow']['22']['inputs']['seed'] = 18446744073709551615
        response = self.command('save_connection', {'id':'exact','base_url':'http://localhost:8188','adapter':'comfyui','comfy_json':json.dumps(c)})
        self.assertEqual(response.status_code, 200, response.text)
        raw = response.json()[0]['comfy_json']
        self.assertEqual(json.loads(raw)['workflow']['22']['inputs']['seed'],18446744073709551615)
        self.assertNotIn('api_key', json.loads(raw))
