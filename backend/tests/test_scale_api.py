from workflow_fixtures import CREATOR_SETTINGS
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from studio.api import create_app


class ScaleApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=TestClient(create_app(Path(self.temp.name),'agent-key','ui-key'))

    def call(self,op,args=None,human=False):
        return self.client.post('/studio/v1/command',json={'operation':op,'arguments':args or {},'actor':'worker'},headers={'Authorization':'Bearer '+('ui-key' if human else 'agent-key')})

    def test_queue_api_worker_roundtrip_and_human_policy_boundary(self):
        args={'name':'Campaign','idea':'Quiet observatory','kind':'campaign','template_id':'ai-film','count':2,'request_id':'campaign','settings':CREATOR_SETTINGS}
        response=self.call('create_batch',args)
        self.assertEqual(response.status_code,200,response.text)
        batch=response.json()
        for op,values in [('update_batch',{'batch_id':batch['id'],'policy':{'paused':True},'expected_revision':batch['revision']}),('set_project_dispatch',{}),('sync_batch_identity',{}),('endorse_recipe',{})]:
            self.assertEqual(self.call(op,values).status_code,403,op)
        self.assertEqual(self.call('create_batch',{**args,'request_id':'policy','policy':{'auto_retry':True}}).status_code,403)
        for project_id in batch['project_ids']:
            p=self.call('get_project',{'project_id':project_id}).json()
            self.call('set_policy',{'project_id':project_id,'policy':{'brief':True},'expected_revision':p['revision']},human=True)
        queue=self.call('production_queue').json()
        self.assertEqual(len(queue['items']),2)
        task=self.call('claim_queue_task',{'request_id':'worker-task','batch_id':batch['id']}).json()
        self.assertEqual(task['actor'],'agent:worker')
        self.assertEqual(self.call('renew_queue_task',{'task_id':task['id']}).status_code,200)
        result=self.call('complete_step',{'project_id':task['project_id'],'step':'brief','output':{'text':'A complete actual brief'},'expected_revision':task['project_revision']})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.call('finish_queue_task',{'task_id':task['id'],'status':'done','note':'Prepared actual brief'}).status_code,200)
        self.assertIn('awaiting_approval',[r['state'] for r in self.call('production_queue').json()['items']])
