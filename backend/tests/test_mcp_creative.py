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

    async def roundtrip(self, root):
        params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('mcp_inprocess_server.py'))],env=dict(os.environ,STUDIO_TEST_DATA=str(root)))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                names={t.name for t in (await client.list_tools()).tools}
                self.assertTrue({'creative_schema','knowledge_catalog','preview_shot','record_take_review','record_job_cost','repair_handoff'}<=names)
                self.assertFalse({'review','set_policy'}&names)
                async def call(name,args=None):
                    result=await client.call_tool(name,args or {})
                    self.assertFalse(result.isError,result.content)
                    if result.structuredContent is not None:
                        return result.structuredContent.get('result',result.structuredContent)
                    return json.loads(next(c.text for c in result.content if c.type=='text'))
                schema=await call('creative_schema');self.assertEqual(schema['schema_version'],2)
                catalog=await call('knowledge_catalog',{'category':'lighting'});self.assertTrue(catalog['entries'])
                p=await call('create_project',{'name':'SDK fixture','template_id':'ai-film','request_id':'sdk'})
                blocked=await client.call_tool('update_production',{'project_id':p['id'],'production':{'require_recorded_checks':False},'expected_revision':p['revision']})
                self.assertTrue(blocked.isError)
                # Human side of the same database; the MCP client cannot perform this operation.
                human=Studio(root/'workflow.db',root/'media',root/'inbox')
                saved=human.save_project_template(p['id'],'SDK saved look','Actual snapshot',['settings'],p['revision'])
                templates=await call('list_templates')
                self.assertIn(saved['id'],[t['id'] for t in templates])
                snapshot=await call('get_saved_template',{'template_id':saved['id']})
                self.assertEqual(snapshot['sections'],['settings'])
                p=await call('apply_project_template',{'project_id':p['id'],'template_id':saved['id'],'sections':['settings'],'expected_revision':p['revision'],'template_revision':saved['revision']})
                p=human.set_policy(p['id'],{'brief':False,'script':False},p['revision'])
                for step in ['brief','script']:
                    p=await call('complete_step',{'project_id':p['id'],'step':step,'output':{'text':'Actual '+step+' fixture'},'expected_revision':p['revision']})
                p=await call('update_shots',{'project_id':p['id'],'shots':[{'title':'Window','image_prompt':'Traveler beside window','motion_prompt':'Turns toward light','direction':{'camera':{'lens':'85mm'},'lighting':{'world_source':'North wall window'}}}],'expected_revision':p['revision']})
                preview=await call('preview_shot',{'project_id':p['id'],'shot_id':p['shots'][0]['id']});self.assertIn('85mm',preview['image']['prompt'])
                task=await call('claim_generation',{'project_id':p['id'],'request_id':'sdk-image'})
                self.assertIn('North wall window',task['handoff']['prompt'])
                file=root/'inbox'/'synthetic.png';Image.new('RGB',(32,18),'orange').save(file)
                result=await call('return_generation',{'job_id':task['job']['id'],'output_path':str(file)})
                p=await call('get_project',{'project_id':p['id']})
                p=await call('record_take_review',{'project_id':p['id'],'asset_id':result['asset']['id'],'review':{'criteria':{c:True for c in p['assets'][0]['required_checks']},'inspected':['image'],'notes':'Synthetic fixture inspected','defect':''},'expected_revision':p['revision']})
                self.assertEqual(p['assets'][0]['review']['actor'],'agent:sdk-test')
                bundle=await call('export_generation_package',{'project_id':p['id']})
                with zipfile.ZipFile(bundle['path']) as archive:
                    manifest=json.loads(archive.read('manifest.json'))
                    self.assertEqual(manifest['shots'][0]['direction']['camera']['lens'],'85mm')
                    self.assertIn('source_coverage',manifest)
                self.assertEqual((await call('next_action',{'project_id':p['id']}))['action'],'await_approval')
                batch=await call('create_batch',{'name':'SDK batch','idea':'One observatory mystery','request_id':'sdk-batch','count':1,'kind':'episodes','template_id':'ai-film'})
                queue=await call('production_queue',{'batch_id':batch['id']})
                self.assertEqual(len(queue['items']),1)
                task=await call('claim_queue_task',{'request_id':'sdk-work','batch_id':batch['id']})
                self.assertEqual(task['status'],'active')
                await call('renew_queue_task',{'task_id':task['id']})
                prepared=await call('complete_step',{'project_id':task['project_id'],'step':'brief','output':{'text':'Actual batch brief'},'expected_revision':task['project_revision']})
                await call('finish_queue_task',{'task_id':task['id'],'status':'done','note':'Actual brief prepared'})
                self.assertEqual((await call('production_queue',{'batch_id':batch['id']}))['items'][0]['state'],'awaiting_approval')
