import copy
import io
import tempfile
import unittest
from pathlib import Path

import httpx
from PIL import Image

try:
    from studio.comfy import validate_config, build_workflow, validate_installed, execute_comfy, ComfyError
except ImportError:
    validate_config = build_workflow = validate_installed = execute_comfy = ComfyError = None


def config(kind='image'):
    return {'kind': kind, 'workflow': {'11': {'class_type': 'Encode', 'inputs': {'text': 'original'}}, '12': {'class_type': 'Encode', 'inputs': {'text': ''}}, '22': {'class_type': 'Sampler', 'inputs': {'seed': 123, 'steps': 8, 'positive': ['11', 0]}}, '33': {'class_type': 'Save', 'inputs': {'images': ['22', 0]}}},
            'bindings': {'positive': {'node': '11', 'input': 'text'}, 'negative': {'node': '12', 'input': 'text'}}, 'output_node': '33'}


class ComfyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.assertIsNotNone(validate_config, 'ComfyUI workflow connector is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.handoff = {'kind': 'image', 'prompt': 'A painted boat', 'negative_prompt': '', 'references': [], 'image_requirements': {'mode': 'generate'}}

    def test_bindings_preserve_template_and_sampler_settings(self):
        c = config()
        before = copy.deepcopy(c)
        wf = build_workflow(validate_config(c), self.handoff, {})
        self.assertEqual(wf['11']['inputs']['text'], 'A painted boat')
        self.assertEqual(wf['22']['inputs'], before['workflow']['22']['inputs'])
        self.assertEqual(c, before)

    def test_ui_graph_missing_targets_duplicate_targets_and_invalid_kind_reject(self):
        bad = []
        c = config(); c['workflow'] = {'nodes': [], 'links': []}; bad.append(c)
        c = config(); c['output_node'] = '99'; bad.append(c)
        c = config(); c['bindings']['negative'] = c['bindings']['positive']; bad.append(c)
        c = config(); c['kind'] = 'audio'; bad.append(c)
        c = config(); c['bindings']['positive']['input'] = 'absent'; bad.append(c)
        for c in bad:
            with self.subTest(config=c), self.assertRaises(ValueError): validate_config(c)

    def test_reference_mapping_is_explicit_and_edit_requires_source(self):
        c = config()
        with self.assertRaises(ValueError):
            build_workflow(c, {**self.handoff, 'image_requirements': {'mode': 'edit'}}, {})
        c['workflow']['44'] = {'class_type': 'LoadImage', 'inputs': {'image': 'old.png'}}
        c['bindings']['references'] = [{'slot': 'subject', 'node': '44', 'input': 'image'}]
        with self.assertRaises(ValueError): build_workflow(c, self.handoff, {})
        result = build_workflow(c, {**self.handoff, 'references': [{'slot': 'subject', 'id': 'a'}]}, {'subject': 'uploaded.png'})
        self.assertEqual(result['44']['inputs']['image'], 'uploaded.png')

    def test_missing_nodes_models_and_unmapped_file_inputs_fail_preflight(self):
        c = config()
        schema = {'Encode': {'input': {'required': {'text': ['STRING']}}}, 'Sampler': {'input': {'required': {'seed': ['INT'], 'steps': ['INT'], 'positive': ['CONDITIONING']}}}, 'Save': {'output_node': True, 'input': {'required': {'images': ['IMAGE']}}}}
        validate_installed(c, schema)
        with self.assertRaises(ValueError): validate_installed(c, {})
        c['workflow']['22']['inputs']['model_name'] = 'missing.safetensors'
        schema['Sampler']['input']['required']['model_name'] = [['installed.safetensors']]
        with self.assertRaises(ValueError): validate_installed(c, schema)
        c = config(); c['workflow']['44'] = {'class_type':'LoadVideo','inputs':{'file':'unrelated.mp4'}}
        del schema['Sampler']['input']['required']['model_name']
        schema['LoadVideo'] = {'input':{'required':{'file':['STRING',{'video_upload':True}]}}}
        with self.assertRaises(ValueError): validate_installed(c, schema)

    async def test_authorization_is_rechecked_immediately_before_remote_submission(self):
        requests = []
        schema = {n['class_type']: {'output_node': n['class_type'] == 'Save', 'input': {'required': {k: ['STRING'] for k in n['inputs']}}} for n in config()['workflow'].values()}
        def handler(r):
            requests.append(r.url.path)
            return httpx.Response(200, json=schema)
        def blocked(): raise ValueError('Project was paused')
        async with httpx.AsyncClient(base_url='http://localhost', transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ValueError, 'paused'):
                await execute_comfy(client, config(), self.handoff, self.root, self.root, lambda _: None, before_submit=blocked)
        self.assertNotIn('/prompt', requests)

    async def test_execution_downloads_only_mapped_output_and_reports_prompt_id(self):
        buf = io.BytesIO(); Image.new('RGB', (8, 8), 'blue').save(buf, format='PNG')
        seen = []
        schema = {n['class_type']: {'output_node': n['class_type'] == 'Save', 'input': {'required': {k: ['STRING'] for k in n['inputs']}}} for n in config()['workflow'].values()}
        def handler(request):
            seen.append(str(request.url))
            if request.url.path == '/object_info': return httpx.Response(200, json=schema)
            if request.url.path == '/prompt': return httpx.Response(200, json={'prompt_id': 'remote-1'})
            if request.url.path == '/history/remote-1': return httpx.Response(200, json={'remote-1': {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'preview': {'images': [{'filename': 'wrong.png'}]}, '33': {'images': [{'filename': 'actual.png', 'subfolder': '', 'type': 'output'}]}}}})
            return httpx.Response(200, content=buf.getvalue())
        ids = []
        async with httpx.AsyncClient(base_url='http://localhost:8188', transport=httpx.MockTransport(handler)) as client:
            path = await execute_comfy(client, config(), self.handoff, self.root, self.root, ids.append, poll_interval=0)
        self.assertEqual(path.read_bytes(), buf.getvalue())
        self.assertEqual(ids, ['remote-1'])
        self.assertTrue(any('actual.png' in url for url in seen))
        self.assertFalse(any('wrong.png' in url for url in seen))

    async def test_remote_error_and_timeout_never_return_success(self):
        schema = {n['class_type']: {'output_node': n['class_type'] == 'Save', 'input': {'required': {k: ['STRING'] for k in n['inputs']}}} for n in config()['workflow'].values()}
        for history in [{'x': {'status': {'status_str': 'error', 'completed': False}, 'outputs': {}}}, {}]:
            def handler(r):
                return httpx.Response(200, json=schema if r.url.path == '/object_info' else {'prompt_id': 'x'} if r.url.path == '/prompt' else history)
            async with httpx.AsyncClient(base_url='http://localhost', transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(ValueError):
                    await execute_comfy(client, config(), self.handoff, self.root, self.root, lambda _: None, poll_interval=0, attempts=2)

    async def test_video_output_and_reference_path_validation(self):
        c = config('video')
        schema = {n['class_type']: {'output_node': n['class_type'] == 'Save', 'input': {'required': {k: ['STRING'] for k in n['inputs']}}} for n in c['workflow'].values()}
        def handler(r):
            if r.url.path == '/object_info': return httpx.Response(200, json=schema)
            if r.url.path == '/prompt': return httpx.Response(200, json={'prompt_id': 'v'})
            if r.url.path == '/history/v': return httpx.Response(200, json={'v': {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'33': {'gifs': [{'filename': 'result.mp4', 'type': 'output'}]}}}})
            return httpx.Response(200, content=b'validated later by studio MP4 validator')
        async with httpx.AsyncClient(base_url='http://localhost', transport=httpx.MockTransport(handler)) as client:
            path = await execute_comfy(client, c, {**self.handoff, 'kind': 'video'}, self.root, self.root, lambda _: None, poll_interval=0)
        self.assertEqual(path.suffix, '.mp4')
        bad = {**self.handoff, 'references': [{'id': 'a', 'slot': 'subject', 'path': str(self.root.parent/'outside.png')}]}
        async with httpx.AsyncClient(base_url='http://localhost', transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(ValueError): await execute_comfy(client, config(), bad, self.root, self.root, lambda _: None)

    async def test_actual_image_reference_upload_is_wired_into_submitted_workflow(self):
        c = config()
        c['workflow']['44'] = {'class_type':'LoadImage','inputs':{'image':'old.png'}}
        c['bindings']['references'] = [{'slot':'subject','node':'44','input':'image'}]
        source=self.root/'source.png'; Image.new('RGBA',(8,8),(255,0,0,128)).save(source)
        seen=[]
        schema = {n['class_type']: {'output_node': n['class_type']=='Save','input':{'required':{k:['STRING'] for k in n['inputs']}}} for n in c['workflow'].values()}
        def handler(r):
            seen.append(r)
            if r.url.path=='/object_info': return httpx.Response(200,json=schema)
            if r.url.path=='/upload/image':
                self.assertIn(source.read_bytes(),r.read())
                return httpx.Response(200,json={'name':'uploaded.png','subfolder':'orchestra'})
            if r.url.path=='/prompt':
                import json
                graph=json.loads(r.read())['prompt']
                self.assertEqual(graph['44']['inputs']['image'],'orchestra/uploaded.png')
                self.assertEqual(graph['22']['inputs']['steps'],8)
                return httpx.Response(200,json={'prompt_id':'source-job'})
            if r.url.path=='/history/source-job': return httpx.Response(200,json={'source-job':{'status':{'completed':True,'status_str':'success'},'outputs':{'33':{'images':[{'filename':'actual.png','type':'output'}]}}}})
            return httpx.Response(200,content=source.read_bytes())
        handoff={**self.handoff,'references':[{'id':'ref','slot':'subject','path':str(source),'kind':'image'}]}
        async with httpx.AsyncClient(base_url='http://localhost',transport=httpx.MockTransport(handler)) as client:
            result=await execute_comfy(client,c,handoff,self.root,self.root,lambda _:None,poll_interval=0)
        with Image.open(result) as image: self.assertEqual(image.mode,'RGBA')
        self.assertEqual(sum(r.url.path=='/prompt' for r in seen),1)

    async def test_oversize_download_fails_and_removes_partial_file(self):
        from unittest.mock import patch
        schema = {n['class_type']: {'output_node':n['class_type']=='Save','input':{'required':{k:['STRING'] for k in n['inputs']}}} for n in config()['workflow'].values()}
        def handler(r):
            if r.url.path=='/object_info': return httpx.Response(200,json=schema)
            if r.url.path=='/prompt': return httpx.Response(200,json={'prompt_id':'large'})
            if r.url.path=='/history/large': return httpx.Response(200,json={'large':{'status':{'completed':True},'outputs':{'33':{'images':[{'filename':'large.png'}]}}}})
            return httpx.Response(200,content=b'123456789')
        with patch('studio.comfy.MAX_DOWNLOAD_BYTES',8,create=True):
            async with httpx.AsyncClient(base_url='http://localhost',transport=httpx.MockTransport(handler)) as client:
                with self.assertRaisesRegex(ValueError,'limit'):
                    await execute_comfy(client,config(),self.handoff,self.root,self.root,lambda _:None,poll_interval=0)
        self.assertEqual(list(self.root.glob('*.png')),[])
