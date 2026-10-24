import copy
import inspect
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from studio.api import create_app
from studio.workflow import Studio
from studio.store import StudioError


class SavedTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.studio=Studio(self.root/'db',self.root/'media',self.root/'inbox')
        self.p=self.studio.create_project('Winning look','ai-film')

    def capture(self, sections=None):
        self.assertTrue(hasattr(self.studio,'save_project_template'),'Reusable project snapshots are not implemented')
        return self.studio.save_project_template(self.p['id'],'Amber drama','Worked well in our pilot',sections or ['settings','workflow','story'],self.p['revision'])

    def test_snapshot_survives_source_changes_deletion_and_restart(self):
        p=self.p
        p=self.studio.update_settings(p['id'],{'lens':'85mm','custom_video_template':'{motion}. Keep amber light.'},p['revision'],'user')
        p=self.studio.set_policy(p['id'],{'brief':False},p['revision'])
        p=self.studio.update_production(p['id'],{'defaults':{'lighting':{'technique':'Rembrandt'}},'resources':{'limit':30},'capabilities':{'model':'Observed only here'},'bible':[{'id':'hero','name':'Hero','kind':'character','asset_ids':['private-media-id']}]},p['revision'],'user')
        shots=copy.deepcopy(p['shots']);shots[1]['direction']['action']['continuity_from']=shots[0]['id'];shots[0]['direction']['references']=[{'slot':'face','asset_id':'private-media-id','role':'character','version':1}]
        self.p=self.studio.update_shots(p['id'],shots,p['revision'],'user')
        saved=self.capture()
        self.p=self.studio.update_settings(p['id'],{'lens':'24mm'},self.p['revision'],'user')
        self.studio.delete_project(p['id'],self.p['revision'])
        reopened=Studio(self.root/'db',self.root/'media',self.root/'inbox')
        clone=reopened.create_project('New story',saved['id'])
        self.assertEqual(clone['settings']['lens'],'85mm')
        self.assertEqual(clone['production']['defaults']['lighting']['technique'],'Rembrandt')
        self.assertFalse(clone['approval_policy']['brief'])
        self.assertEqual(clone['shots'][1]['direction']['action']['continuity_from'],clone['shots'][0]['id'])
        self.assertNotEqual(clone['shots'][0]['id'],self.p['shots'][0]['id'])
        self.assertFalse(clone['assets'] or clone['jobs'] or clone['documents'])
        self.assertTrue(all(v['status']=='draft' for v in clone['steps'].values()))
        self.assertEqual(clone['production']['bible'][0]['asset_ids'],[])
        self.assertEqual(clone['shots'][0]['direction']['references'],[])
        self.assertIsNone(clone['production']['resources']['limit'])
        self.assertEqual(clone['production']['capabilities']['model'],'')
        self.assertEqual(reopened.list_saved_templates()[0]['name'],'Amber drama')

    def test_selective_apply_preserves_unselected_content_and_rejects_stale_revision(self):
        self.p=self.studio.update_settings(self.p['id'],{'lens':'85mm'},self.p['revision'],'user')
        saved=self.capture(['settings'])
        target=self.studio.create_project('Target','ugc')
        before=copy.deepcopy(target)
        result=self.studio.apply_project_template(target['id'],saved['id'],['settings'],target['revision'],saved['revision'],'user')
        self.assertEqual(result['settings']['lens'],'85mm')
        self.assertEqual([{k:v for k,v in s.items() if k!='input_versions'} for s in result['shots']],before['shots'])
        self.assertEqual(result['approval_policy'],before['approval_policy'])
        self.assertEqual(result['production']['story'],before['production']['story'])
        with self.assertRaises(StudioError):
            self.studio.apply_project_template(target['id'],saved['id'],['settings'],target['revision'],saved['revision'],'user')
        self.assertEqual(self.studio.get(target['id'])['revision'],result['revision'])

    def test_rename_delete_and_empty_selection_validation(self):
        saved=self.capture()
        renamed=self.studio.rename_project_template(saved['id'],'Amber portrait','Successful portrait look',saved['revision'])
        self.assertEqual(renamed['name'],'Amber portrait')
        with self.assertRaises(StudioError):self.studio.delete_project_template(saved['id'],saved['revision'])
        self.studio.delete_project_template(saved['id'],renamed['revision'])
        self.assertEqual(self.studio.list_saved_templates(),[])
        with self.assertRaises(StudioError):self.studio.create_project('Missing',saved['id'])
        with self.assertRaises(StudioError):self.studio.save_project_template(self.p['id'],'Empty','',[],self.p['revision'])

    def test_successful_shot_look_can_be_saved_without_reusing_its_story(self):
        self.assertTrue(hasattr(self.studio,'save_project_template'))
        self.assertIn('settings_shot_id',inspect.signature(self.studio.save_project_template).parameters,'Templates need an optional shot-look source')
        p=self.p
        shots=copy.deepcopy(p['shots']);shots[0]['direction']['camera']['lens']='135mm portrait';shots[0]['direction']['lighting']['technique']='Soft north window'
        p=self.studio.update_shots(p['id'],shots,p['revision'],'user')
        saved=self.studio.save_project_template(p['id'],'Portrait look','',['settings'],p['revision'],settings_shot_id=p['shots'][0]['id'])
        clone=self.studio.create_project('Different story',saved['id'])
        self.assertEqual(clone['production']['defaults']['camera']['lens'],'135mm portrait')
        self.assertEqual(clone['production']['defaults']['lighting']['technique'],'Soft north window')
        self.assertEqual(clone['shots'][0]['image_prompt'],'')
        self.assertEqual(clone['production']['defaults']['action']['primary_action'],'')

    def test_settings_only_apply_does_not_bind_entities_from_unselected_story(self):
        p=self.p
        self.p=self.studio.update_production(p['id'],{'bible':[{'id':'source-hero','name':'Original hero','kind':'character'}], 'defaults':{'action':{'visible_entities':['source-hero']},'sound':{'speaker_id':'source-hero'}}},p['revision'],'user')
        saved=self.capture()
        target=self.studio.create_project('Unrelated story','ugc')
        p=self.studio.apply_project_template(target['id'],saved['id'],['settings'],target['revision'],saved['revision'],'user')
        self.assertEqual(p['production']['defaults']['action']['visible_entities'],[])
        self.assertEqual(p['production']['defaults']['sound']['speaker_id'],'')

    def test_story_only_apply_reconciles_old_default_links_without_changing_the_look(self):
        from studio.preflight import preflight
        saved=self.capture(['story'])
        p=self.studio.create_project('Different cast','ugc')
        p=self.studio.update_production(p['id'],{'bible':[{'id':'old-hero','name':'Old hero','kind':'character'}], 'defaults':{'camera':{'lens':'135mm'},'action':{'visible_entities':['old-hero'],'continuity_from':p['shots'][0]['id']},'sound':{'speaker_id':'old-hero'},'references':[{'slot':'old-face','asset_id':'old-face-file','role':'character','entity_id':'old-hero','version':1}]}},p['revision'],'user')
        p=self.studio.apply_project_template(p['id'],saved['id'],['story'],p['revision'],saved['revision'],'user')
        self.assertEqual(preflight(p)['errors'],0)
        d=p['production']['defaults']
        self.assertEqual(d['camera']['lens'],'135mm')
        self.assertEqual(d['action']['visible_entities'],[])
        self.assertEqual(d['sound']['speaker_id'],'')
        self.assertEqual(d['action']['continuity_from'],'')
        self.assertEqual(d['references'],[])

    def test_apply_supersedes_pending_outputs_and_blocks_running_provider(self):
        saved=self.capture(['story'])
        target=self.studio.create_project('Target','ai-film')
        def seed(p):
            p['assets']=[{'id':'old','kind':'image','stale':False,'shot_id':p['shots'][0]['id'],'path':'kept.png'}]
            p['shots'][0]['image_asset']='old'
            p['jobs']=[{'id':'pending','status':'awaiting_external_output','shot_id':p['shots'][0]['id'],'kind':'image'}]
        target=self.studio.mutate(target['id'],target['revision'],seed)
        updated=self.studio.apply_project_template(target['id'],saved['id'],['story'],target['revision'],saved['revision'],'user')
        self.assertEqual(updated['jobs'][0]['status'],'superseded')
        self.assertTrue(updated['assets'][0]['stale'])
        self.assertEqual(updated['assets'][0]['path'],'kept.png')
        updated=self.studio.mutate(updated['id'],updated['revision'],lambda p:p['jobs'][0].update(status='running'))
        with self.assertRaises(StudioError):self.studio.apply_project_template(updated['id'],saved['id'],['story'],updated['revision'],saved['revision'],'user')

    def test_api_agents_can_reuse_settings_but_not_change_policy_through_templates(self):
        app=create_app(self.root/'api','agent-secret','human-secret');client=TestClient(app)
        def command(op,args=None,human=False):
            return client.post('/studio/v1/command',json={'operation':op,'arguments':args or {}},headers={'Authorization':'Bearer '+('human-secret' if human else 'agent-secret')})
        p=command('create_project',{'name':'Source','template_id':'ugc'}).json()
        p=command('set_policy',{'project_id':p['id'],'policy':{'brief':False},'expected_revision':p['revision']},True).json()
        args={'project_id':p['id'],'name':'Good UGC','description':'','sections':['settings','workflow'],'expected_revision':p['revision']}
        self.assertEqual(command('save_project_template',args).status_code,403)
        response=command('save_project_template',args,True)
        self.assertEqual(response.status_code,200,response.text)
        saved=response.json()
        self.assertTrue(any(t['id']==saved['id'] for t in command('list_templates').json()))
        clone=command('create_project',{'name':'Agent start','template_id':saved['id']}).json()
        self.assertFalse(clone['approval_policy']['brief'],'New agent projects start with approvals disabled')
        apply={'project_id':clone['id'],'template_id':saved['id'],'sections':['workflow'],'expected_revision':clone['revision'],'template_revision':saved['revision']}
        self.assertEqual(command('apply_project_template',apply).status_code,403)
        contract=command('get_workflow_contract',{'project_id':clone['id']}).json()
        self.assertEqual(command('acknowledge_workflow_contract',{'project_id':clone['id'],'contract_version':contract['contract_version'],'expected_revision':contract['revision']}).status_code,200)
        apply['sections']=['settings']
        self.assertEqual(command('apply_project_template',apply).status_code,200)
