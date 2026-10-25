"""Public-API calibration contract with real PNGs and separate credentials."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from studio.api import create_app
from test_generation_setup import selection


class CalibrationWorkflowTests(unittest.TestCase):
    def test_creator_rejection_repair_acceptance_and_once_per_project_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with TestClient(create_app(root, 'executor-token', 'creator-token')) as client:
                def request(op, args=None, human=False):
                    return client.post('/studio/v1/command', headers={'Authorization':'Bearer '+('creator-token' if human else 'executor-token')},
                                       json={'operation':op,'arguments':args or {},'actor':'calibration-fixture'})
                def call(op, args=None, human=False):
                    response = request(op,args,human)
                    self.assertEqual(response.status_code,200,response.text[:1000])
                    return response.json()
                p = call('create_project',{'name':'API calibration fixture','template_id':'custom','output_type':'video'})
                pid = p['id']
                def current(): return call('get_project',{'project_id':pid})
                def write(op, fields, human=False):
                    return call(op,{'project_id':pid,'expected_revision':current()['revision'],**fields},human)
                def acknowledge():
                    contract = call('get_workflow_contract',{'project_id':pid})
                    write('acknowledge_workflow_contract',{'contract_version':contract['contract_version']})
                self.assertEqual(call('start_project_setup',{'project_id':pid})['missing_media_kinds'],['image','video'])
                write('set_generation_setup',{'setup':{'version':1,'image':selection(),'video':selection('video')}})
                self.assertEqual(call('start_project_setup',{'project_id':pid})['questions'],[])
                write('update_settings',{'settings':{'creative_intake':{'vision':'Translucent amber worlds','art_style':'Coherent botanical photography','purpose':'Calibration film'}}},True)
                for step in ['brief','script']: write('complete_step',{'step':step,'output':{'text':'Synthetic creator fixture '+step}},True)
                p = write('update_shots',{'shots':[{'title':'Garden','image_prompt':'A translucent amber flower'}, {'title':'Ocean','image_prompt':'A folded turquoise sea'}]},True)
                representative = p['shots'][0]['id']
                acknowledge()
                def claim_and_inspect(key):
                    result=write('claim_generation',{'request_id':key})
                    job,h=result['job'],result['handoff']
                    self.assertIsNotNone(job,result)
                    self.assertNotIn('handoff',job)
                    self.assertEqual(h['negative_prompt'],'','Built-in image tool has no separate negative argument')
                    execution={'tool':'image_gen.imagegen','prompt':h['prompt'],'negative_prompt':'','references':h['references'],
                               'arguments':{'prompt':h['prompt'],'transparent_background':False}}
                    call('record_generation_execution',{'job_id':job['id'],'execution':execution,'expected_revision':current()['revision']})
                    image=root/'inbox'/(key+'.png'); Image.new('RGB',(32,18),'orange').save(image)
                    returned=call('return_generation',{'job_id':job['id'],'output_path':str(image)})
                    asset=returned['asset']
                    p=current(); take=next(a for a in p['assets'] if a['id']==asset['id'])
                    self.assertEqual(take['execution_state'],'match')
                    write('record_take_review',{'asset_id':asset['id'],'review':{'criteria':{c:True for c in take['required_checks']},'inspected':['image'],'notes':'Inspected synthetic PNG only'}})
                    return job,asset
                first,asset=claim_and_inspect('first')
                self.assertEqual(call('next_action',{'project_id':pid})['action'],'await_calibration_approval')
                self.assertIsNone(write('claim_generation',{'request_id':'blocked'})['job'])
                self.assertEqual(call('claim_queue_task',{'request_id':'queue-blocked'})['status'],'idle')
                call('save_connection',{'id':'fixture','name':'Offline fixture','base_url':'https://fixture.invalid','enabled':True,'max_requests':1},True)
                self.assertEqual(request('run_provider',{'job_id':first['id'],'connection_id':'fixture'}).status_code,409)
                connection=next(c for c in call('studio_capabilities')['connections'] if c['id']=='fixture')
                self.assertEqual(connection['used_requests'],0)
                self.assertEqual(request('review_calibration',{'project_id':pid,'asset_id':asset['id'],'approve':True,'expected_revision':current()['revision']}).status_code,403)
                write('review_calibration',{'asset_id':asset['id'],'approve':False,'note':'Fixture creator rejects composition'},True)
                self.assertTrue(any(a['id']==asset['id'] for a in current()['assets']))
                write('revise_shot',{'shot_id':representative,'kind':'image','reason':'Repair rejected composition'})
                second,repaired=claim_and_inspect('repair')
                self.assertEqual(second['shot_id'],representative)
                write('review_calibration',{'asset_id':repaired['id'],'approve':True,'note':'Fixture creator accepts amber treatment'},True)
                next_job=write('claim_generation',{'request_id':'next-world'})['job']
                self.assertNotEqual(next_job['shot_id'],representative)
                self.assertEqual(call('start_project_setup',{'project_id':pid})['questions'],[])
                write('update_settings',{'settings':{'image_generator':'flux_image'}},True)
                self.assertIn('image',call('start_project_setup',{'project_id':pid})['missing_media_kinds'])
