import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from studio import paths
from studio.assets import checked_file
from studio.store import StudioError


class PhysicalDataPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def resolver(self, value):
        self.assertTrue(hasattr(paths, 'resolve_writable_root'), 'Stable physical root resolver missing')
        return paths.resolve_writable_root(value)

    def redirected(self, logical, physical):
        original = Path.resolve
        def resolve(value, *args, **kwargs):
            if value.parent == logical and value.name.startswith('.orchestra-probe-'):
                return physical/value.name
            return original(value, *args, **kwargs)
        return patch.object(Path, 'resolve', resolve)

    def test_directory_file_divergence_selects_stable_physical_root_and_cleans_probe(self):
        logical, physical = self.root/'logical', self.root/'physical'
        physical.mkdir()
        with self.redirected(logical, physical):
            self.assertEqual(self.resolver(logical), physical)
        self.assertEqual(list(logical.iterdir()), [])
        self.assertEqual(list(physical.iterdir()), [])

    def test_competing_state_is_not_merged_or_credentials_read(self):
        logical, physical = self.root/'logical', self.root/'physical'
        logical.mkdir(); physical.mkdir()
        for folder in [logical, physical]:
            (folder/'workflow.db').write_text('different state', encoding='utf-8')
            (folder/'agent.token').write_text('private-secret', encoding='utf-8')
        with self.redirected(logical, physical), self.assertRaisesRegex(ValueError, 'competing') as caught:
            self.resolver(logical)
        self.assertNotIn('private-secret', str(caught.exception))
        self.assertTrue((logical/'workflow.db').exists())
        self.assertTrue((physical/'workflow.db').exists())
        (physical/'workflow.db').unlink()
        with self.redirected(logical, physical), self.assertRaisesRegex(ValueError, 'competing'):
            self.resolver(logical)

    def test_explicit_physical_root_import_and_containment(self):
        root = self.resolver(self.root/'physical')
        inbox = root/'inbox'; inbox.mkdir()
        image = inbox/'real.png'; Image.new('RGB', (16,16)).save(image)
        self.assertEqual(checked_file(image, [inbox], 'image')[0], image)
        other = root/'inbox-sibling'; other.mkdir()
        escape = other/'escape.png'; Image.new('RGB', (16,16)).save(escape)
        for candidate in [escape, inbox/'..'/'inbox-sibling'/'escape.png']:
            with self.assertRaises(StudioError) as caught: checked_file(candidate, [inbox], 'image')
            self.assertEqual(caught.exception.code, 'path_not_allowed')

    def test_runtime_rejects_other_root_pid_and_not_ready_without_credentials(self):
        import studio_desktop
        runtime = {'api_url':'http://127.0.0.1:43123', 'instance_id':'fixture', 'schema_version':2,
                   'ready':True, 'service_pid':123, 'data_root':str(self.root)}
        (self.root/'desktop-runtime.json').write_text(json.dumps(runtime), encoding='utf-8')
        parsed = studio_desktop.load_desktop_runtime(self.root)
        self.assertEqual(parsed.get('service_pid'), 123)
        for changes in [{'ready':False}, {'service_pid':0}, {'data_root':str(self.root/'other')}]:
            (self.root/'desktop-runtime.json').write_text(json.dumps({**runtime, **changes}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'backend_unavailable'): studio_desktop.load_desktop_runtime(self.root)
