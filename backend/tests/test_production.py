import copy
import shutil
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
import test_creative
from studio.store import StudioError


class ProductionTests(unittest.TestCase):
    setUp = test_creative.CreativeTests.setUp
    prepare = test_creative.CreativeTests.prepare
    def image_return(self, request='one'):
        task=self.studio.claim_next(self.p['id'],'agent',request)
        file=self.studio.inbox/(request+'.png')
        Image.new('RGB',(32,18),'orange').save(file)
        result=self.studio.return_result(task['job']['id'],str(file),'agent')
        self.p=self.studio.get_project(self.p['id'])
        return task,result

    def test_selective_revision_preserves_unrelated_image(self):
        p=self.prepare()
        p=self.studio.update_shots(p['id'],[p['shots'][0],{'title':'Other','image_prompt':'Other image','motion_prompt':'Still'}],p['revision'],'agent')
        self.p=p
        first,_=self.image_return('first')
        second,_=self.image_return('second')
        p=self.p
        changed=copy.deepcopy(p['shots'])
        changed[0]['image_prompt']='New traveler appearance'
        updated=self.studio.update_shots(p['id'],changed,p['revision'],'agent')
        self.assertIsNone(updated['shots'][0]['image_asset'])
        self.assertEqual(updated['shots'][1]['image_asset'],p['shots'][1]['image_asset'])

    def test_confirmed_unsupported_aspect_reopens_an_existing_media_step(self):
        self.prepare();self.image_return()
        p=self.p
        p=self.studio.update_production(p['id'],{'capabilities':{'confirmed':True,'model':'Observed fixture','source':'Test observation','observed_at':'2026-10-21','aspects':['9:16']}},p['revision'],'user')
        self.assertEqual(self.studio.next_action(p['id'])['action'],'resolve_preflight')

    def test_motion_change_preserves_keyframe_and_rejects_incompatible_old_take(self):
        self.prepare();_,returned=self.image_return()
        p=self.p
        shots=copy.deepcopy(p['shots']);shots[0]['motion_prompt']='A different action'
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        self.assertEqual(p['shots'][0]['image_asset'],returned['asset']['id'])
        self.assertTrue(hasattr(self.studio,'select_take'),'Missing take selection')
        shots[0]['image_prompt']='Different identity'
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        with self.assertRaises(StudioError):
            self.studio.select_take(p['id'],returned['asset']['id'],p['revision'],'user')

    def test_required_qc_waits_for_recorded_full_clip_inspection(self):
        p=self.prepare()
        p=self.studio.update_production(p['id'],{'require_recorded_checks':True},p['revision'],'user')
        p=self.studio.set_policy(p['id'],{'visual_direction':False},p['revision'])
        self.p=p
        _,returned=self.image_return()
        self.assertEqual(self.studio.next_action(p['id'])['action'],'record_quality')
        p=self.studio.record_take_review(p['id'],returned['asset']['id'],{'criteria':{'Identity and composition serve the shot':True},'inspected':['image'],'notes':'Inspected fixture','defect':''},self.p['revision'],'agent')
        self.assertEqual(self.studio.next_action(p['id'])['kind'],'video')
        self.assertEqual(p['assets'][0]['review']['actor'],'agent')

    def test_budget_unknown_cost_blocks_and_retry_reserves_once(self):
        p=self.prepare()
        p=self.studio.update_production(p['id'],{'resources':{'limit':5,'unit':'credits'}},p['revision'],'user')
        action=self.studio.next_action(p['id'])
        self.assertEqual(action['action'],'resolve_resources')
        p=self.studio.update_production(p['id'],{'resources':{'image_cost':2,'cost_evidence':'Observed test cost'}},p['revision'],'user')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.studio.claim_next(p['id'],'agent','same'),range(2)))
        self.assertEqual(results[0]['job']['id'],results[1]['job']['id'])
        self.assertTrue(hasattr(self.studio,'production_metrics'),'Missing resource ledger')
        self.assertEqual(self.studio.production_metrics(p['id'])['reserved_or_spent'],2)

    def test_reported_overrun_cannot_be_hidden_by_cancel_or_unit_change(self):
        p=self.prepare()
        p=self.studio.update_production(p['id'],{'resources':{'limit':3,'image_cost':2,'cost_evidence':'Observed test cost'}},p['revision'],'user')
        job=self.studio.claim_next(p['id'],'agent','cost')['job']
        self.assertTrue(hasattr(self.studio,'record_job_cost'),'Missing cost reporting')
        p=self.studio.get_project(p['id'])
        p=self.studio.record_job_cost(p['id'],job['id'],4,'Provider invoice',p['revision'],'agent')
        self.studio.cancel_job(job['id'],'agent')
        self.assertEqual(self.studio.production_metrics(p['id'])['reserved_or_spent'],4)
        self.assertEqual(self.studio.next_action(p['id'])['action'],'resolve_resources')
        p=self.studio.get_project(p['id'])
        with self.assertRaises(StudioError):
            self.studio.update_production(p['id'],{'resources':{'unit':'USD'}},p['revision'],'user')

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_real_continuation_frame_is_registered_and_repair_preserves_original(self):
        self.prepare();self.image_return()
        p=self.p
        p=self.studio.set_policy(p['id'],{'visual_direction':False},p['revision'])
        task=self.studio.claim_next(p['id'],'agent','motion')
        file=self.studio.inbox/'fixture.mp4'
        subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=orange:s=32x18:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(file)],capture_output=True,check=True)
        result=self.studio.return_result(task['job']['id'],str(file),'agent')
        p=self.studio.get_project(p['id'])
        self.assertTrue(hasattr(self.studio,'extract_continuation'),'Missing real frame extraction')
        p=self.studio.extract_continuation(p['id'],result['asset']['id'],p['revision'],'agent')
        frame=next(a for a in p['assets'] if a.get('source_video')==result['asset']['id'])
        with Image.open(frame['path']) as img:self.assertEqual(img.size,(32,18))
        handoff=self.studio.repair_handoff(p['id'],frame['id'],'Fix one corner','',p['revision'],'agent')
        self.assertEqual(handoff['original']['id'],frame['id'])
        self.assertIn('preserve',handoff)
