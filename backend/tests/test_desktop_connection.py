import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class DesktopConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / 'existing AppData' / 'studio_data'
        self.runtime = dict(api_url='http://127.0.0.1:43123', instance_id='live-desktop',
                            service_pid=123, data_root=str(self.root), schema_version=2, ready=True)

    def module(self):
        from studio import desktop_connection
        return desktop_connection

    def test_private_connection_is_outside_appdata_and_cleanup_is_owner_bound(self):
        connection = self.module()
        with patch.object(Path, 'home', return_value=self.home):
            connection.publish_connection(self.runtime, 'bridge-secret')
            file = connection.connection_file(self.root)
            self.assertTrue(file.is_relative_to(self.home / '.orchestra'))
            self.assertEqual(connection.read_connection(self.root)['agent_token'], 'bridge-secret')
            self.assertFalse(self.root.exists(), 'Discovery must not create/move project data')
            connection.remove_connection(self.root, 'another-instance')
            self.assertTrue(file.exists())
            connection.remove_connection(self.root, 'live-desktop')
            self.assertFalse(file.exists())

    def test_bridge_discovers_active_root_without_writable_probe_or_shadow_credentials(self):
        import studio_desktop
        connection = self.module()
        with patch.object(Path, 'home', return_value=self.home):
            connection.publish_connection(self.runtime, 'correct-agent-only-token')
            with patch.object(studio_desktop, 'resolve_writable_root', side_effect=AssertionError('MCP must not probe writable roots')), patch.object(studio_desktop, 'verify_desktop_runtime') as health:
                runtime, token = studio_desktop.discover_desktop(self.root)
            self.assertEqual(runtime['instance_id'], 'live-desktop')
            self.assertEqual(token, 'correct-agent-only-token')
            health.assert_called_once()

    def test_wrong_root_remote_runtime_and_stale_health_fail_closed(self):
        import studio_desktop
        connection = self.module()
        with patch.object(Path, 'home', return_value=self.home):
            connection.publish_connection(self.runtime, 'private-agent-token')
            file = connection.connection_file(self.root)
            original = file.read_text()
            for changes in [{'data_root': str(self.home / 'another')}, {'api_url': 'http://example.com:1234'}, {'ready': False}]:
                payload = json.loads(original)
                payload['runtime'].update(changes)
                file.write_text(json.dumps(payload))
                with self.assertRaisesRegex(ValueError, 'backend_unavailable'):
                    studio_desktop.discover_desktop(self.root)
            file.write_text(original)
            with patch.object(studio_desktop, 'verify_desktop_runtime', side_effect=ValueError('backend_unavailable')):
                with self.assertRaisesRegex(ValueError, 'backend_unavailable'):
                    studio_desktop.discover_desktop(self.root)

    def test_bridge_credential_is_agent_only_and_never_exported(self):
        from fastapi.testclient import TestClient
        from studio.api import create_app
        with TestClient(create_app(self.root, 'original-agent', 'original-browser', bridge_token='private-bridge')) as client:
            response = client.post('/studio/v1/command', headers={'Authorization': 'Bearer private-bridge'}, json={'operation': 'studio_capabilities'})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('private-bridge', response.text)
            response = client.post('/studio/v1/command', headers={'Authorization': 'Bearer private-bridge'}, json={'operation': 'list_deleted'})
            self.assertEqual(response.status_code, 403)
            for token in ['original-agent', 'original-browser']:
                response = client.post('/studio/v1/command', headers={'Authorization': 'Bearer ' + token}, json={'operation': 'studio_capabilities'})
                self.assertEqual(response.status_code, 200)

    def test_legacy_runtime_still_connects_without_creating_a_shared_record(self):
        import studio_desktop
        connection = self.module()
        self.root.mkdir(parents=True)
        (self.root / 'desktop-runtime.json').write_text(json.dumps(self.runtime))
        with patch.object(Path, 'home', return_value=self.home), patch.object(studio_desktop, 'verify_desktop_runtime'):
            runtime, token = studio_desktop.discover_desktop(self.root)
            self.assertEqual(runtime['instance_id'], 'live-desktop')
            self.assertIsNone(token)
            self.assertFalse(connection.connection_file(self.root).exists())

    def test_malformed_private_record_has_no_secret_in_diagnostic(self):
        import studio_desktop
        connection = self.module()
        with patch.object(Path, 'home', return_value=self.home):
            connection.publish_connection(self.runtime, 'private-agent-token')
            connection.connection_file(self.root).write_text('{"agent_token":"private-agent-token"}')
            with self.assertRaisesRegex(ValueError, 'Discovery root:') as caught:
                studio_desktop.discover_desktop(self.root)
            self.assertNotIn('private-agent-token', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
