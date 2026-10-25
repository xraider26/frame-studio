import io
import json
import unittest
from PIL import Image
from fastapi.testclient import TestClient
import test_calibration as fixtures
from studio.api import create_app
from unittest.mock import patch
from test_generation_setup import selection
import asyncio
import httpx


class CreatorChatTests(unittest.TestCase):
    setUp = fixtures.CalibrationTests.setUp
    prepare = fixtures.CalibrationTests.prepare
    take = fixtures.CalibrationTests.take
    inspect = fixtures.CalibrationTests.inspect

    def client(self):
        app = create_app(self.root / 'api', 'agent', 'browser')
        self.s = app.state.studio
        return TestClient(app)

    def ack(self, p):
        c = self.s.get_workflow_contract(p['id'])
        self.s.acknowledge_workflow_contract(p['id'], c['contract_version'], p['revision'], 'agent:test')

    def request(self, client, p, operation, arguments, instruction='Please make the land less rugged', request_id='chat-1'):
        return client.post('/studio/v1/command', headers={'Authorization': 'Bearer agent'}, json={'operation':'creator_decision','actor':'test','arguments':{'project_id':p['id'],'expected_revision':p['revision'],'request_id':request_id,'user_instruction':instruction,'operation':operation,'arguments':arguments}})

    def test_modification_rejects_pending_take_and_authorizes_revision_in_one_write(self):
        with self.client() as client:
            p, a = self.take(self.prepare()); p = self.inspect(p, a); self.ack(p)
            response = self.request(client,p,'request_revision',{'shot_id':a['shot_id'],'asset_id':a['id'],'kind':'image'})
            self.assertEqual(response.status_code,200,response.text)
            current = self.s.get(p['id'])
            self.assertEqual(current['revision'],p['revision']+1)
            self.assertEqual(current['calibration']['history'][-1]['decision'],'reject')
            self.assertEqual(current['calibration']['history'][-1]['actor'],'creator_chat:test')
            self.assertEqual(current['creator_decisions'][-1]['user_instruction'],'Please make the land less rugged')
            self.assertEqual(current['creator_decisions'][-1]['authority'],'user_instruction_relayed')
            self.assertEqual(self.s.next_action(p['id'])['action'],'generate')
            self.assertTrue(__import__('pathlib').Path(a['path']).exists())
            again = self.request(client,p,'request_revision',{'shot_id':a['shot_id'],'asset_id':a['id'],'kind':'image'})
            self.assertEqual(again.status_code,200,again.text)
            self.assertEqual(self.s.get(p['id'])['revision'],current['revision'])

    def test_chat_acceptance_policy_and_target_checks_do_not_weaken_normal_agent_access(self):
        with self.client() as client:
            p, a = self.take(self.prepare()); p=self.inspect(p,a); self.ack(p)
            self.assertEqual(self.request(client,p,'review_calibration',{'asset_id':a['id'],'approve':True},'').status_code,400)
            bad=self.request(client,p,'request_revision',{'shot_id':a['shot_id'],'asset_id':'wrong','kind':'image'})
            self.assertEqual(bad.status_code,409,bad.text)
            self.assertEqual(self.s.get(p['id'])['revision'],p['revision'])
            good=self.request(client,p,'review_calibration',{'asset_id':a['id'],'approve':True},'Approved, use this style')
            self.assertEqual(good.status_code,200,good.text)
            p=self.s.get(p['id']);self.ack(p)
            policy=self.request(client,p,'set_policy',{'policy':{'final_review':True}},'Require my final review',request_id='policy-1')
            self.assertEqual(policy.status_code,200,policy.text)
            self.assertTrue(self.s.get(p['id'])['approval_policy']['final_review'])
            ordinary=client.post('/studio/v1/command',headers={'Authorization':'Bearer agent'},json={'operation':'set_policy','arguments':{'project_id':p['id'],'expected_revision':p['revision'],'policy':{'final_review':False}}})
            self.assertEqual(ordinary.status_code,403)

    def test_conflicting_duplicate_missing_instruction_and_cross_project_are_rejected(self):
        with self.client() as client:
            p=self.prepare();self.ack(p)
            result=self.request(client,p,'set_policy',{'policy':{'brief':False}},'Keep brief review off')
            self.assertEqual(result.status_code,200,result.text)
            conflict=self.request(client,p,'set_policy',{'policy':{'brief':True}},'Require brief review')
            self.assertEqual(conflict.status_code,409,conflict.text)
            current=self.s.get(p['id']);self.ack(current)
            bad=self.request(client,current,'set_policy',{'project_id':'another','policy':{}},'Change this project',request_id='cross')
            self.assertEqual(bad.status_code,400,bad.text)

    def test_owned_job_upload_returns_actual_bytes_without_shared_filesystem(self):
        with self.client() as client:
            p=self.prepare();self.ack(p)
            claim=self.s.claim_next(p['id'],'agent:test','upload-job')
            p=self.s.get(p['id']);self.ack(p)
            h=claim['handoff'] if 'handoff' in claim else claim['job']['handoff']
            self.s.record_generation_execution(claim['job']['id'],{'tool':'fixture','prompt':h['prompt'],'negative_prompt':h['negative_prompt'],'references':[],'arguments':{}},p['revision'],'agent:test')
            data=io.BytesIO();Image.new('RGB',(32,18),'orange').save(data,format='PNG')
            url='/studio/v1/jobs/'+claim['job']['id']+'/output'
            denied=client.post(url,headers={'Authorization':'Bearer agent'},data={'actor':'other'},files={'file':('fixture.png',data.getvalue(),'image/png')})
            self.assertEqual(denied.status_code,403,denied.text)
            result=client.post(url,headers={'Authorization':'Bearer agent'},data={'actor':'test'},files={'file':('fixture.png',data.getvalue(),'image/png')})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['asset']['kind'],'image')
            again=client.post(url,headers={'Authorization':'Bearer agent'},data={'actor':'test'},files={'file':('fixture.png',data.getvalue(),'image/png')})
            self.assertEqual(again.status_code,200,again.text)
            self.assertEqual(again.json()['asset']['id'],result.json()['asset']['id'])
            self.assertFalse(any(self.s.inbox.glob('upload-*')))

    def test_video_only_and_notes_edits_do_not_imply_image_rejection(self):
        with self.client() as client:
            p,a=self.take(self.prepare());p=self.inspect(p,a);self.ack(p)
            video=selection('video');video['tool_name']='Another video destination'
            response=self.request(client,p,'set_generation_setup',{'setup':{'version':1,'video':video}},'Use another video tool')
            self.assertEqual(response.status_code,200,response.text)
            p=self.s.get(p['id']);self.assertEqual(p['shots'][0]['image_asset'],a['id'])
            self.assertFalse(p['calibration']['history'])
            self.ack(p)
            response=self.request(client,p,'update_settings',{'settings':{'creative_intake':{**p['settings']['creative_intake'],'purpose':'Backdrop montage'}}},'Use the images as backdrops',request_id='notes')
            self.assertEqual(response.status_code,200,response.text)
            p=self.s.get(p['id']);self.assertEqual(p['shots'][0]['image_asset'],a['id']);self.assertFalse(p['calibration']['history'])

    def test_direct_visual_edit_rejects_pending_image_atomically(self):
        with self.client() as client:
            p,a=self.take(self.prepare());p=self.inspect(p,a);self.ack(p)
            shots=__import__('copy').deepcopy(p['shots']);shots[0]['image_prompt']='A simpler translucent garden'
            response=self.request(client,p,'update_shots',{'shots':shots},'Simplify this garden')
            self.assertEqual(response.status_code,200,response.text)
            p=self.s.get(p['id']);self.assertEqual(p['calibration']['history'][-1]['decision'],'reject')
            self.assertEqual(p['shots'][0]['image_prompt'],'A simpler translucent garden')
            self.assertEqual(self.s.next_action(p['id'])['action'],'generate')

    def test_template_side_effect_and_decision_receipt_roll_back_together(self):
        with self.client() as client:
            p=self.prepare();self.ack(p)
            args={'name':'Saved from chat','sections':['settings']}
            with patch('studio.creator_chat.append_decision',side_effect=RuntimeError('injected receipt failure')):
                with self.assertRaises(RuntimeError):self.request(client,p,'save_project_template',args,'Save my settings as a template')
            self.assertEqual(self.s.list_saved_templates(),[])
            self.assertEqual(self.s.get(p['id'])['revision'],p['revision'])
            response=self.request(client,p,'save_project_template',args,'Save my settings as a template')
            self.assertEqual(response.status_code,200,response.text)
            first=response.json();current=self.s.get(p['id'])
            duplicate=self.request(client,current,'save_project_template',args,'Save my settings as a template')
            self.assertEqual(duplicate.status_code,200,duplicate.text)
            self.assertEqual(duplicate.json()['result'],first['result'])
            self.assertEqual(len(self.s.list_saved_templates()),1)

    def test_revision_of_approved_take_records_rejection_without_erasing_old_file(self):
        with self.client() as client:
            p,a=self.take(self.prepare());p=self.inspect(p,a)
            p=self.s.review_calibration(p['id'],a['id'],True,'Accept fixture',p['revision'],'user');self.ack(p)
            response=self.request(client,p,'request_revision',{'shot_id':a['shot_id'],'asset_id':a['id'],'kind':'image'},'Change this approved image',request_id='approved-revision')
            self.assertEqual(response.status_code,200,response.text)
            p=self.s.get(p['id']);self.assertEqual(p['calibration']['history'][-1]['decision'],'reject')
            self.assertTrue(__import__('pathlib').Path(a['path']).exists())

    def test_chat_reference_modification_and_template_revision_routing(self):
        with self.client() as client:
            p,a=self.take(self.prepare());p=self.inspect(p,a);self.ack(p)
            file=self.s.inbox/'new-reference.png';Image.new('RGB',(16,16),'blue').save(file)
            response=self.request(client,p,'import_reference',{'path':str(file),'name':'New style','kind':'image'},'Use this blue style reference')
            self.assertEqual(response.status_code,200,response.text)
            p=self.s.get(p['id']);self.assertEqual(p['calibration']['history'][-1]['decision'],'reject')
            template=self.s.save_project_template(p['id'],'Saved','',['settings'],p['revision'])
            p=self.s.get(p['id']);self.ack(p)
            response=self.request(client,p,'rename_project_template',{'template_id':template['id'],'template_revision':template['revision'],'name':'Renamed'},'Rename the template',request_id='rename')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(self.s.get_saved_template(template['id'])['name'],'Renamed')

    def test_uploaded_chat_reference_can_cross_filesystem_views(self):
        with self.client() as client:
            p,a=self.take(self.prepare());p=self.inspect(p,a);self.ack(p)
            image=io.BytesIO();Image.new('RGB',(16,16),'blue').save(image,format='PNG')
            decision={'project_id':p['id'],'expected_revision':p['revision'],'request_id':'upload-ref','user_instruction':'Use this blue reference','operation':'import_reference','arguments':{'path':'not-visible-to-server/reference.png','name':'Blue reference','kind':'image'}}
            response=client.post('/studio/v1/creator-reference',headers={'Authorization':'Bearer agent'},data={'actor':'test','decision':json.dumps(decision)},files={'file':('ref.png',image.getvalue(),'image/png')})
            self.assertEqual(response.status_code,200,response.text)
            p=self.s.get(p['id']);self.assertEqual(p['calibration']['history'][-1]['decision'],'reject')
            self.assertEqual(p['creator_decisions'][-1]['authority'],'user_instruction_relayed')
            self.assertTrue(any(a.get('role')=='reference' for a in p['assets']))
            self.assertFalse(any(self.s.inbox.glob('upload-reference-*')))

    def test_provider_receipt_failure_preserves_config_and_delete_restore_is_relayed(self):
        with self.client() as client:
            p=self.prepare();self.ack(p)
            config=self.root/'api'/'connections.json'
            with patch('studio.creator_chat.append_decision',side_effect=RuntimeError('injected')):
                with self.assertRaises(RuntimeError):self.request(client,p,'save_connection',{'id':'local','base_url':'http://localhost:8188','enabled':False},'Save this local connection')
            self.assertFalse(config.exists())
            self.assertEqual(self.s.get(p['id'])['revision'],p['revision'])
            deleted=self.request(client,p,'delete_project',{},'Move this project to trash')
            self.assertEqual(deleted.status_code,200,deleted.text)
            revision=deleted.json()['revision']
            restored=self.request(client,{**p,'revision':revision},'restore_project',{},'Restore that project',request_id='restore')
            self.assertEqual(restored.status_code,200,restored.text)
            self.assertNotIn('deleted_at',self.s.get(p['id']))

    def test_batch_decisions_require_membership_and_commit_member_audits(self):
        with self.client() as client:
            unrelated=self.prepare();self.ack(unrelated)
            batch=self.s.create_batch('Batch','Five worlds','variations','image-custom',2,'chat-batch','user',output_type='image')
            args={'batch_id':batch['id'],'batch_revision':batch['revision'],'policy':{'paused':True}}
            rejected=self.request(client,unrelated,'update_batch',args,'Pause this batch')
            self.assertEqual(rejected.status_code,409,rejected.text)
            member=self.s.get(batch['project_ids'][0]);self.ack(member)
            before=[self.s.get(i)['revision'] for i in batch['project_ids']]
            with patch('studio.creator_chat.append_decision',side_effect=RuntimeError('injected audit failure')):
                with self.assertRaises(RuntimeError):self.request(client,member,'update_batch',args,'Pause this batch')
            self.assertEqual(self.s.get_batch(batch['id'])['revision'],batch['revision'])
            self.assertEqual([self.s.get(i)['revision'] for i in batch['project_ids']],before)
            applied=self.request(client,member,'update_batch',args,'Pause this batch')
            self.assertEqual(applied.status_code,200,applied.text)
            updated=self.s.get_batch(batch['id']);self.assertTrue(updated['paused'])
            for key in batch['project_ids']:
                self.assertEqual(self.s.get(key)['creator_decisions'][-1]['actor'],'creator_chat:test')
            replay=self.request(client,member,'update_batch',args,'Pause this batch')
            self.assertEqual(replay.status_code,200,replay.text)
            self.assertEqual(self.s.get_batch(batch['id'])['revision'],updated['revision'])

    def test_remote_validation_does_not_hold_writer_lock_across_await(self):
        with self.client() as client:
            p=self.prepare();self.ack(p)
            async def delayed(connection_id):
                await asyncio.sleep(0.15)
                return {'valid':True}
            async def exercise():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),base_url='http://test') as http:
                    decision={'operation':'creator_decision','actor':'test','arguments':{'project_id':p['id'],'expected_revision':p['revision'],'request_id':'remote-probe','user_instruction':'Validate the local connection','operation':'validate_connection','arguments':{'connection_id':'fixture'}}}
                    task=asyncio.create_task(http.post('/studio/v1/command',headers={'Authorization':'Bearer agent'},json=decision))
                    await asyncio.sleep(0.03)
                    edited=await http.post('/studio/v1/command',headers={'Authorization':'Bearer browser'},json={'operation':'set_policy','arguments':{'project_id':p['id'],'expected_revision':p['revision'],'policy':{'brief':False}}})
                    self.assertEqual(edited.status_code,200,edited.text)
                    validation=await task
                    self.assertEqual(validation.status_code,409,validation.text)
            with patch.object(client.app.state.providers,'validate_connection',side_effect=delayed):
                asyncio.run(exercise())
