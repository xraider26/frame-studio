import copy
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
from studio.workflow import Studio
from studio.store import StudioError


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.s=Studio(root/'db',root/'media',root/'inbox')

    def batch(self,count=3,policy=None,request='batch-once'):
        self.assertTrue(hasattr(self.s,'create_batch'),'Idea-to-production batches are missing')
        return self.s.create_batch('Observatory stories','A traveler discovers abandoned observatories','episodes','ai-film',count,request,'user',policy=policy)

    def prepare(self,p):
        p=self.s.set_policy(p['id'],{'brief':False,'script':False},p['revision'])
        for step in ['brief','script']:p=self.s.complete_step(p['id'],step,{'text':'Actual '+step},p['revision'],'agent')
        return self.s.update_shots(p['id'],[{**p['shots'][0],'image_prompt':'A real portrait','motion_prompt':'Turns toward window'}],p['revision'],'agent')

    def test_atomic_idempotent_batch_preserves_idea_and_independent_ids_after_restart(self):
        b=self.batch()
        self.assertEqual(len(b['project_ids']),3)
        projects=[self.s.get(i) for i in b['project_ids']]
        self.assertTrue(all(p['production']['brief']['premise']==b['idea'] for p in projects))
        self.assertTrue(all(p['documents']=={} and p['jobs']==[] for p in projects))
        self.assertEqual(len({s['id'] for p in projects for s in p['shots']}),9)
        self.assertEqual(self.batch()['id'],b['id'])
        reopened=Studio(self.s.db_path,self.s.media_root,self.s.inbox)
        self.assertEqual(reopened.get_batch(b['id'])['project_ids'],b['project_ids'])
        for count in [0,101,True]:
            with self.assertRaises(StudioError):self.batch(count,request='invalid-'+str(count))
        original=self.s._build_project
        calls=[]
        def fail(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise StudioError('fixture','Deliberate mid-batch failure')
            return original(*args,**kwargs)
        self.s._build_project=fail
        with self.assertRaises(StudioError):self.batch(3,request='rolled-back')
        self.assertEqual(len(self.s.list_projects()),3)

    def test_queue_leases_are_exclusive_idempotent_and_recover_after_expiry(self):
        b=self.batch(3,{'max_parallel':2})
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks=list(pool.map(lambda n:self.s.claim_queue_task('agent:'+str(n),'request-'+str(n),b['id']),range(2)))
        self.assertEqual(len({t['project_id'] for t in tasks}),2)
        self.assertEqual(self.s.claim_queue_task('agent:0','request-0',b['id'])['id'],tasks[0]['id'])
        self.assertIsNone(self.s.claim_queue_task('agent:2','request-2',b['id']).get('id'))
        task=tasks[0]
        with self.assertRaises(StudioError):self.s.finish_queue_task(task['id'],'agent:wrong','done','')
        with self.assertRaises(StudioError):self.s.finish_queue_task(task['id'],'agent:0','done','No actual work')
        self.s.complete_step(task['project_id'],'brief',{'text':'Prepared actual premise'},task['project_revision'],'agent:0')
        self.s.finish_queue_task(task['id'],'agent:0','done','Brief prepared')
        with self.s.connect() as conn:conn.execute("UPDATE studio_tasks SET expires_at='2000-01-01T00:00:00+00:00' WHERE status='active'")
        expired=self.s.claim_queue_task('agent:1','request-1',b['id'])
        self.assertEqual(expired['status'],'expired','A replay must not advertise an expired lease as active')
        recovered=self.s.claim_queue_task('agent:2','after-expiry',b['id'])
        self.assertIsNotNone(recovered.get('id'))

    def test_pause_and_concurrency_apply_to_direct_generation_claims(self):
        b=self.batch(2,{'max_parallel':1})
        a,z=[self.prepare(self.s.get(i)) for i in b['project_ids']]
        self.s.claim_next(a['id'],'agent','first-image')
        with self.assertRaises(StudioError):self.s.claim_next(z['id'],'agent','over-concurrency')
        p=self.s.set_project_dispatch(a['id'],True,0,a['revision']+1)
        with self.assertRaises(StudioError):self.s.claim_next(a['id'],'agent','paused')
        b=self.s.update_batch(b['id'],{'paused':True},b['revision'])
        self.assertTrue(all(r['state']=='paused' for r in self.s.production_queue(b['id'])['items']))

    def test_hard_batch_budget_blocks_unknown_cost_and_atomic_overrun(self):
        b=self.batch(2,{'budget_limit':3,'unit':'credits','max_parallel':2})
        a,z=[self.prepare(self.s.get(i)) for i in b['project_ids']]
        with self.assertRaises(StudioError):self.s.claim_next(a['id'],'agent','unknown')
        b=self.s.update_batch(b['id'],{'image_cost':2,'cost_evidence':'Observed fixture cost'},b['revision'])
        self.s.claim_next(a['id'],'agent','known')
        with self.assertRaises(StudioError):self.s.claim_next(z['id'],'agent','too-expensive')
        self.assertEqual(self.s.production_queue(b['id'])['batches'][0]['reserved_or_spent'],2)
        current=self.s.get(a['id']);self.s.delete_project(a['id'],current['revision'])
        self.assertEqual(self.s.production_queue(b['id'])['batches'][0]['reserved_or_spent'],2,'Trashed items still carry incurred/reserved cost')
        with self.assertRaises(StudioError):self.s.claim_next(z['id'],'agent','still-too-expensive')

    def test_batch_hard_limit_is_atomic_across_parallel_project_claims(self):
        b=self.batch(2,{'budget_limit':3,'image_cost':2,'cost_evidence':'Observed fixture','max_parallel':2})
        projects=[self.prepare(self.s.get(i)) for i in b['project_ids']]
        def claim(p):
            try:return bool(self.s.claim_next(p['id'],'agent',p['id']).get('job'))
            except StudioError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,projects))
        self.assertEqual(sum(results),1)

    def test_paused_api_provider_start_is_blocked_even_for_an_existing_job(self):
        b=self.batch(1)
        p=self.prepare(self.s.get(b['project_ids'][0]))
        job=self.s.claim_next(p['id'],'agent','existing')['job']
        p=self.s.get(p['id']);self.s.set_project_dispatch(p['id'],True,0,p['revision'])
        self.assertIsNotNone(self.s._dispatch_block(self.s.get(p['id']),'image',existing_job=job['id']))
        from studio.providers import Providers
        providers=Providers(self.s,self.s.db_path.parent/'connections.json')
        providers.save({'id':'fixture','name':'Fixture','base_url':'http://127.0.0.1:8999','enabled':True,'max_requests':1})
        with self.assertRaises(StudioError):providers.submit(job['id'],'fixture')
        self.assertEqual(providers.connections['fixture']['used_requests'],0)

    def test_quality_failure_retries_only_selected_inspected_takes_and_stops_at_limit(self):
        b=self.batch(1,{'auto_retry':True,'retry_limit':1})
        p=self.prepare(self.s.get(b['project_ids'][0]))
        file=self.s.inbox/'fixture.png';Image.new('RGB',(32,18),'orange').save(file)
        task=self.s.claim_next(p['id'],'agent','quality-first')
        result=self.s.return_result(task['job']['id'],str(file),'agent')
        p=self.s.get(p['id'])
        p=self.s.record_take_review(p['id'],result['asset']['id'],{'criteria':{},'inspected':['image'],'defect':'Visible duplicate hand'},p['revision'],'agent')
        self.assertIsNone(p['shots'][0]['image_asset'])
        self.assertEqual(p['shots'][0]['quality_retries']['image'],1)
        self.assertIn('duplicate hand',p['shots'][0]['direction']['quality']['revision_reason'])
        p=self.s.record_take_review(p['id'],result['asset']['id'],{'criteria':{},'inspected':['image'],'defect':'Same old take'},p['revision'],'agent')
        self.assertEqual(p['shots'][0]['quality_retries']['image'],1)
        task=self.s.claim_next(p['id'],'agent','quality-second')
        result=self.s.return_result(task['job']['id'],str(file),'agent');p=self.s.get(p['id'])
        p=self.s.record_take_review(p['id'],result['asset']['id'],{'criteria':{},'inspected':['image'],'defect':'Still incorrect'},p['revision'],'agent')
        self.assertEqual(self.s.next_action(p['id'])['action'],'quality_attention')

    def test_agent_cannot_change_batch_policy_through_create(self):
        self.assertTrue(hasattr(self.s,'create_batch'))
        with self.assertRaises(StudioError):self.s.create_batch('Agent','Idea','variations','custom',2,'agent-policy','agent',policy={'auto_retry':True},allow_policy=False)

    def test_revision_churn_is_not_actual_queue_task_progress(self):
        b=self.batch(1)
        task=self.s.claim_queue_task('agent','no-op',b['id'])
        self.s.mutate(task['project_id'],None,lambda p:None)
        with self.assertRaises(StudioError):self.s.finish_queue_task(task['id'],'agent','done','Only revision changed')
