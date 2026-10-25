from workflow_fixtures import CREATOR_SETTINGS
import asyncio
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from studio.workflow import Studio


class McpCreativeTests(unittest.TestCase):
    def test_real_sdk_stdio_tools_route_to_actual_api_and_keep_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            asyncio.run(self.roundtrip(Path(folder)))

    def test_real_entrypoint_lists_and_invokes_generation_execution_recorder(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from fastapi.testclient import TestClient
        from studio.api import create_app
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);studio=Studio(root/'workflow.db',root/'media',root/'inbox')
            p=studio.create_project('Entrypoint fixture','image-custom',output_type='image',settings=CREATOR_SETTINGS)
            for step in ['brief','script']: p=studio.complete_step(p['id'],step,{'text':'Fixture '+step},p['revision'],'user')
            p=studio.update_shots(p['id'],[{'title':'Garden','image_prompt':'Amber garden'}],p['revision'],'user')
            job=studio.claim_next(p['id'],'agent:entrypoint','entrypoint-fixture')['job']
            execution={'tool':'synthetic-fixture-generator','prompt':job['handoff']['prompt'],'negative_prompt':job['handoff']['negative_prompt'],'references':job['handoff']['references'],'arguments':{'fixture_only':True}}
            api=TestClient(create_app(root,'fixture-agent','fixture-browser'))
            class Handler(BaseHTTPRequestHandler):
                def do_POST(handler):
                    payload=handler.rfile.read(int(handler.headers['Content-Length']))
                    response=api.post(handler.path,content=payload,headers={'Authorization':handler.headers['Authorization'],'Content-Type':'application/json'})
                    handler.send_response(response.status_code);handler.send_header('Content-Type','application/json');handler.end_headers();handler.wfile.write(response.content)
                def log_message(self,*args): pass
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            worker=Thread(target=server.serve_forever,daemon=True);worker.start()
            try: asyncio.run(self.entrypoint_record(root,server.server_port,job,execution,studio.get(p['id'])['revision']))
            finally: server.shutdown();server.server_close();worker.join();api.close()
            saved=studio.find_job(job['id'])[1]['execution']
            self.assertEqual(saved['evidence_source'],'agent_reported');self.assertEqual(saved['validation']['state'],'match')
            self.assertEqual(saved['prompt'],'Amber garden. Medium shot; 35mm. technique: Soft directional light. Cinematic realism; Warm amber')

    async def entrypoint_record(self,root,port,job,execution,revision):
        env=dict(os.environ,STUDIO_DATA_DIR=str(root),STUDIO_API_URL=f'http://127.0.0.1:{port}',STUDIO_AGENT_TOKEN='fixture-agent',STUDIO_CLIENT_NAME='entrypoint')
        env.pop('STUDIO_DESKTOP_INSTANCE',None)
        params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).resolve().parents[1]/'studio_mcp.py')],env=env)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                self.assertTrue({'record_generation_execution', 'get_context', 'source_catalog'} <= tools.keys())
                self.assertEqual(tools['claim_generation'].inputSchema['properties']['response_format']['default'], 'compact')
                self.assertIn('detail', tools['get_project'].inputSchema['properties'])
                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    self.assertFalse(result.isError, result.content)
                    return result.structuredContent or json.loads(next(c.text for c in result.content if c.type == 'text'))
                project_id = job['handoff']['project_id']
                contract = await call('get_workflow_contract', {'project_id': project_id})
                await call('acknowledge_workflow_contract', {'project_id': project_id, 'contract_version': contract['contract_version'], 'expected_revision': revision})
                claim = await call('claim_generation', {'project_id': project_id, 'request_id': job['request_id'], 'expected_revision': revision})
                self.assertEqual(claim['schema_version'], 3)
                self.assertNotIn('handoff', claim['job'])
                self.assertEqual(claim['handoff']['prompt'], execution['prompt'])
                ref = claim['handoff']['context_refs']['recipe']
                self.assertEqual((await call('get_context', ref))['version'], ref['version'])
                summary = await call('get_project', {'project_id': project_id})
                self.assertNotIn('handoff', summary['jobs'][0])
                diagnostic = await call('get_job', {'job_id': job['id'], 'detail': 'full'})
                self.assertEqual(diagnostic['handoff']['schema_version'], 2)
                legacy = await call('claim_generation', {'project_id': project_id, 'request_id': job['request_id'], 'expected_revision': revision, 'response_format': 'legacy'})
                self.assertEqual(legacy['job']['handoff'], legacy['handoff'])
                sources = await call('source_catalog', {'source_id': 'appearance', 'detail': 'full'})
                self.assertEqual(len(sources['rules']), 1)
                result=await client.call_tool('record_generation_execution',{'job_id':job['id'],'execution':execution,'expected_revision':revision})
                self.assertFalse(result.isError,result.content)

    async def roundtrip(self, root):
        params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('mcp_inprocess_server.py'))],env=dict(os.environ,STUDIO_TEST_DATA=str(root)))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                names={t.name for t in (await client.list_tools()).tools}
                self.assertTrue({'creative_schema','knowledge_catalog','preview_shot','record_take_review','record_job_cost','repair_handoff','get_workflow_contract','acknowledge_workflow_contract','start_project_setup','set_generation_setup'}<=names)
                self.assertFalse({'review','set_policy'}&names)
                async def call(name,args=None):
                    result=await client.call_tool(name,args or {})
                    self.assertFalse(result.isError,result.content)
                    if result.structuredContent is not None:
                        return result.structuredContent.get('result',result.structuredContent)
                    return json.loads(next(c.text for c in result.content if c.type=='text'))
                async def acknowledge(project_id):
                    contract=await call('get_workflow_contract',{'project_id':project_id})
                    return await call('acknowledge_workflow_contract',{'project_id':project_id,'contract_version':contract['contract_version'],'expected_revision':contract['revision']})
                initial=await call('start_project_setup',{'output_type':'image'})
                self.assertEqual(initial['questions'][0]['media_kinds'],['image'])
                skeleton=await call('create_project',{'name':'Setup SDK fixture','output_type':'image','generation_setup':{'version':1}})
                self.assertEqual((await call('next_action',{'project_id':skeleton['id']}))['step'],'generation_setup')
                skeleton=await call('set_generation_setup',{'project_id':skeleton['id'],'setup':{'version':1,'image':{'executor':'agent_builtin','tool_name':'Built-in image tool','profile':'general_image','model':None,'model_version_status':'managed','connection_id':None,'selection_source':'creator_statement','source_text':'Use built-in images'}},'expected_revision':skeleton['revision']})
                self.assertIsNone(skeleton['generation_setup']['image']['model'])
                self.assertEqual((await call('start_project_setup',{'project_id':skeleton['id']}))['questions'],[])
                schema=await call('creative_schema');self.assertEqual(schema['schema_version'],2)
                catalog=await call('knowledge_catalog',{'category':'lighting'});self.assertTrue(catalog['entries'])
                p=await call('create_project',{'name':'SDK fixture','template_id':'ai-film','request_id':'sdk','settings':CREATOR_SETTINGS})
                blocked=await client.call_tool('update_production',{'project_id':p['id'],'production':{'require_recorded_checks':False},'expected_revision':p['revision']})
                self.assertTrue(blocked.isError)
                # Human side of the same database; the MCP client cannot perform this operation.
                human=Studio(root/'workflow.db',root/'media',root/'inbox')
                saved=human.save_project_template(p['id'],'SDK saved look','Actual snapshot',['settings'],p['revision'])
                templates=await call('list_templates')
                self.assertIn(saved['id'],[t['id'] for t in templates])
                snapshot=await call('get_saved_template',{'template_id':saved['id']})
                self.assertEqual(snapshot['sections'],['settings'])
                await acknowledge(p['id'])
                p=await call('apply_project_template',{'project_id':p['id'],'template_id':saved['id'],'sections':['settings'],'expected_revision':p['revision'],'template_revision':saved['revision']})
                p=human.set_policy(p['id'],{'brief':False,'script':False,'visual_direction':True},p['revision'])
                await acknowledge(p['id'])
                for step in ['brief','script']:
                    p=await call('complete_step',{'project_id':p['id'],'step':step,'output':{'text':'Actual '+step+' fixture'},'expected_revision':p['revision']})
                p=await call('update_shots',{'project_id':p['id'],'shots':[{'title':'Window','image_prompt':'Traveler beside window','motion_prompt':'Turns toward light','direction':{'camera':{'lens':'85mm'},'lighting':{'world_source':'North wall window'}}}],'expected_revision':p['revision']})
                preview=await call('preview_shot',{'project_id':p['id'],'shot_id':p['shots'][0]['id']});self.assertIn('85mm',preview['image']['prompt'])
                task=await call('claim_generation',{'project_id':p['id'],'request_id':'sdk-image','expected_revision':p['revision']})
                self.assertIn('North wall window',task['handoff']['prompt'])
                file=root/'inbox'/'synthetic.png';Image.new('RGB',(32,18),'orange').save(file)
                current=await call('get_project',{'project_id':p['id']})
                await call('record_generation_execution',{'job_id':task['job']['id'],'execution':{'tool':'synthetic-fixture-generator','prompt':task['handoff']['prompt'],'negative_prompt':task['handoff'].get('negative_prompt',''),'references':task['handoff'].get('references',[]),'arguments':{'fixture_only':True}},'expected_revision':current['revision']})
                result=await call('return_generation',{'job_id':task['job']['id'],'output_path':str(file)})
                p=await call('get_project',{'project_id':p['id']})
                p=await call('record_take_review',{'project_id':p['id'],'asset_id':result['asset']['id'],'review':{'criteria':{c:True for c in p['assets'][0]['required_checks']},'inspected':['image'],'notes':'Synthetic fixture inspected','defect':''},'expected_revision':p['revision']})
                self.assertEqual(p['assets'][0]['review']['actor'],'agent:sdk-test')
                bundle=await call('export_generation_package',{'project_id':p['id']})
                with zipfile.ZipFile(bundle['path']) as archive:
                    manifest=json.loads(archive.read('manifest.json'))
                    self.assertEqual(manifest['shots'][0]['direction']['camera']['lens'],'85mm')
                    self.assertIn('source_coverage',manifest)
                self.assertEqual((await call('next_action',{'project_id':p['id']}))['action'],'await_calibration_approval')
                p=human.review_calibration(p['id'],result['asset']['id'],True,'Creator accepts this synthetic fixture baseline',p['revision'],'user')
                self.assertEqual((await call('next_action',{'project_id':p['id']}))['action'],'await_approval')
                batch=await call('create_batch',{'name':'SDK batch','idea':'One observatory mystery','request_id':'sdk-batch','count':1,'kind':'episodes','template_id':'ai-film','settings':CREATOR_SETTINGS})
                bp=human.get(batch['project_ids'][0])
                human.set_policy(bp['id'],{'brief':True},bp['revision'])
                queue=await call('production_queue',{'batch_id':batch['id']})
                self.assertEqual(len(queue['items']),1)
                task=await call('claim_queue_task',{'request_id':'sdk-work','batch_id':batch['id']})
                self.assertEqual(task['status'],'active')
                await call('renew_queue_task',{'task_id':task['id']})
                await acknowledge(task['project_id'])
                prepared=await call('complete_step',{'project_id':task['project_id'],'step':'brief','output':{'text':'Actual batch brief'},'expected_revision':task['project_revision']})
                await call('finish_queue_task',{'task_id':task['id'],'status':'done','note':'Actual brief prepared'})
                self.assertEqual((await call('production_queue',{'batch_id':batch['id']}))['items'][0]['state'],'awaiting_approval')
