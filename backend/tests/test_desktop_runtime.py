"""Desktop packaging boundaries: immutable resources, mutable data, and live discovery."""
import json
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch

try:
    import studio_desktop
    from studio import paths
except ImportError:
    studio_desktop = None
    paths = None


class DesktopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(studio_desktop, 'Desktop service entry point is missing')
        self.assertIsNotNone(paths, 'Shared frozen resource paths are missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_runtime(self, api_url='http://127.0.0.1:43123', instance_id='desktop-test'):
        (self.root / 'desktop-runtime.json').write_text(json.dumps({
            'api_url': api_url, 'instance_id': instance_id,
        }), encoding='utf-8')

    def test_development_paths_preserve_checkout_defaults(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(paths.resource_root(), Path(__file__).resolve().parents[2])
            self.assertEqual(paths.data_root(), Path(__file__).resolve().parents[2] / 'studio_data')

    def test_frozen_paths_do_not_write_beside_executable_or_internal_bundle(self):
        executable = self.root / 'resources' / 'backend' / 'FrameStudioService.exe'
        with patch.dict(os.environ, {'APPDATA': str(self.root / 'profile')}, clear=True), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)):
            self.assertEqual(paths.resource_root(), self.root / 'resources' / 'studio')
            self.assertEqual(paths.data_root(), self.root / 'profile' / 'Frame Studio' / 'studio_data')

    def test_explicit_resource_and_data_roots_override_layout(self):
        with patch.dict(os.environ, {'STUDIO_RESOURCE_ROOT': str(self.root / 'public'), 'STUDIO_DATA_DIR': str(self.root / 'private')}):
            self.assertEqual(paths.resource_root(), self.root / 'public')
            self.assertEqual(paths.data_root(), self.root / 'private')

    def test_capabilities_publish_actual_frozen_executable_and_explicit_app_data(self):
        from fastapi.testclient import TestClient
        from studio.api import create_app
        executable = self.root / 'install with spaces' / 'FrameStudioService.exe'
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)), patch.dict(os.environ, {'STUDIO_RESOURCE_ROOT': str(Path(__file__).resolve().parents[2]), 'STUDIO_DATA_DIR': str(self.root / 'wrong-global-data'), 'STUDIO_AGENT_TOKEN': 'never-export-this'}):
            with TestClient(create_app(self.root / 'actual-data', 'agent-test', 'browser-test')) as client:
                for token in ['agent-test', 'browser-test']:
                    result = client.post('/studio/v1/command', json={'operation': 'studio_capabilities'}, headers={'Authorization': 'Bearer ' + token})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.json()['mcp_launch'], {'command': str(executable), 'args': ['mcp', '--data-dir', str(self.root / 'actual-data')], 'env': {}, 'desktop': True})
                    self.assertNotIn('never-export-this', result.text)

    def test_capabilities_publish_development_python_and_api_without_secrets(self):
        from fastapi.testclient import TestClient
        from studio.api import create_app
        checkout = Path(__file__).resolve().parents[2]
        with patch.object(sys, 'frozen', False, create=True), patch.dict(os.environ, {'STUDIO_API_URL': 'http://127.0.0.1:45001', 'STUDIO_AGENT_TOKEN': 'never-export-this'}):
            with TestClient(create_app(self.root, 'agent-test', 'browser-test')) as client:
                result = client.post('/studio/v1/command', json={'operation': 'studio_capabilities'}, headers={'Authorization': 'Bearer agent-test'})
                self.assertEqual(result.json()['mcp_launch'], {'command': sys.executable, 'args': [str(checkout / 'backend' / 'studio_mcp.py')], 'env': {'STUDIO_DATA_DIR': str(self.root), 'STUDIO_API_URL': 'http://127.0.0.1:45001'}, 'desktop': False})
                self.assertNotIn('never-export-this', result.text)

    def test_ffprobe_validation_hides_windows_worker_console(self):
        from studio.assets import checked_file
        source = self.root / 'video.mp4'
        source.write_bytes(b'external-ffprobe-fixture')
        probe_result = subprocess.CompletedProcess(['ffprobe'], 0, stdout=b'{"streams":[{"codec_type":"video","width":16,"height":9}],"format":{"format_name":"mov,mp4","duration":"1"}}')
        with patch('studio.assets.shutil.which', return_value='ffprobe'), patch('studio.assets.subprocess.run', return_value=probe_result) as run:
            _, metadata = checked_file(source, [self.root], 'video')
        self.assertEqual(metadata['duration'], 1)
        self.assertEqual(run.call_args.kwargs.get('creationflags'), subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def test_runtime_accepts_only_loopback_explicit_port(self):
        for url in ['http://127.0.0.1:43123', 'http://localhost:43123', 'http://[::1]:43123']:
            with self.subTest(url=url):
                self.write_runtime(url)
                self.assertEqual(studio_desktop.load_desktop_runtime(self.root), {'api_url': url, 'instance_id': 'desktop-test'})

    def test_runtime_rejects_remote_credentials_missing_ports_and_extra_url_parts(self):
        for url in ['http://example.com:80', 'http://127.0.0.2:80', 'https://localhost:43123', 'http://localhost', 'http://localhost:0', 'http://localhost:65536', 'http://user@localhost:43123', 'http://localhost:43123/studio', 'http://localhost:43123/', 'http://localhost:43123?token=x', 'http://localhost:43123#x', 'http://localhost:43123?']:
            with self.subTest(url=url):
                self.write_runtime(url)
                with self.assertRaisesRegex(ValueError, 'backend_unavailable'):
                    studio_desktop.load_desktop_runtime(self.root)

    def test_runtime_requires_nonce_and_valid_json_object(self):
        for content in ['[]', 'null', '{', '{"api_url":"http://localhost:43123"}', '{"api_url":"http://localhost:43123","instance_id":""}']:
            with self.subTest(content=content):
                (self.root / 'desktop-runtime.json').write_text(content, encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'backend_unavailable'):
                    studio_desktop.load_desktop_runtime(self.root)

    def test_mcp_closed_app_is_clear_failure_with_no_stdout(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'studio_desktop.py'), 'mcp', '--data-dir', str(self.root)], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('backend_unavailable', result.stderr)
        self.assertIn('Open Frame Studio', result.stderr)

    def test_health_reports_desktop_instance(self):
        from fastapi.testclient import TestClient
        from studio.api import create_app
        with patch.dict(os.environ, {'STUDIO_DESKTOP_INSTANCE': 'nonce-for-desktop'}):
            app = create_app(self.root)
            with TestClient(app) as client:
                self.assertEqual(client.get('/health').json()['instance_id'], 'nonce-for-desktop')

    def test_desktop_bridge_missing_token_instructs_open_desktop(self):
        import studio_mcp
        with patch.object(studio_mcp, 'DATA', self.root), patch.dict(os.environ, {'STUDIO_DESKTOP_INSTANCE': 'test-nonce'}):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop('STUDIO_AGENT_TOKEN', None)
                with self.assertRaisesRegex(ValueError, 'Open Frame Studio'):
                    asyncio.run(studio_mcp.command('list_projects'))

    def test_desktop_bridge_refuses_unready_instance_before_sending_token(self):
        import studio_mcp
        posted = []

        class UnreadyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"service":"frame-studio","status":"starting","instance_id":"test-nonce"}')

            def do_POST(self):
                posted.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'[]')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), UnreadyHandler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        Thread(target=server.serve_forever, daemon=True).start()
        with patch.object(studio_mcp, 'API', f'http://127.0.0.1:{server.server_port}'), patch.dict(os.environ, {'STUDIO_AGENT_TOKEN': 'private-token', 'STUDIO_DESKTOP_INSTANCE': 'test-nonce'}):
            with self.assertRaisesRegex(ValueError, 'backend_unavailable'):
                asyncio.run(studio_mcp.command('list_projects'))
        self.assertEqual(posted, [])

    def test_discovery_verifies_live_service_and_instance(self):
        payload = {'status': 'ok', 'service': 'frame-studio', 'instance_id': 'live-instance'}

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), HealthHandler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        Thread(target=server.serve_forever, daemon=True).start()
        runtime = {'api_url': f'http://127.0.0.1:{server.server_port}', 'instance_id': 'live-instance'}
        self.assertIsNone(studio_desktop.verify_desktop_runtime(runtime))
        for changed in [{'instance_id': 'stale-instance'}, {'service': 'another-app'}, {'status': 'starting'}]:
            previous = payload.copy()
            payload.update(changed)
            with self.assertRaisesRegex(ValueError, 'backend_unavailable'):
                studio_desktop.verify_desktop_runtime(runtime)
            payload.clear()
            payload.update(previous)


if __name__ == '__main__':
    unittest.main()
