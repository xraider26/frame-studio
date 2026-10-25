from workflow_fixtures import return_fixture
import copy
import shutil
import subprocess
import zipfile
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
        result=return_fixture(self.studio, task['job']['id'],str(file),'agent')
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

    def test_inherited_project_quality_criteria_cannot_be_skipped(self):
        p=self.prepare()
        p=self.studio.update_production(p['id'],{'require_recorded_checks':True,'defaults':{'quality':{'criteria':['Glasses and coat match the canonical portrait']}}},p['revision'],'user')
        p=self.studio.set_policy(p['id'],{'visual_direction':False},p['revision']);self.p=p
        _,result=self.image_return('qc-inherited')
        p=self.studio.record_take_review(p['id'],result['asset']['id'],{'criteria':{'Identity and composition serve the shot':True},'inspected':['image']},self.p['revision'],'agent')
        action=self.studio.next_action(p['id'])
        self.assertEqual(action['action'],'record_quality')
        self.assertIn('Glasses and coat match the canonical portrait',action['criteria'])
        p=self.studio.record_take_review(p['id'],result['asset']['id'],{'criteria':{c:True for c in action['criteria']},'inspected':['image']},p['revision'],'agent')
        self.assertEqual(self.studio.next_action(p['id'])['kind'],'video')
        p=self.studio.update_production(p['id'],{'defaults':{'quality':{'criteria':['New inherited requirement']}}},p['revision'],'user')
        self.assertEqual(p['shots'][0]['image_asset'],result['asset']['id'])
        self.assertEqual(self.studio.next_action(p['id'])['action'],'record_quality')
        shots=copy.deepcopy(p['shots']);shots[0]['direction']['quality']['criteria']=['Shot override']
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        self.assertIn('Shot override',self.studio.next_action(p['id'])['criteria'])
        self.assertNotIn('New inherited requirement',self.studio.next_action(p['id'])['criteria'])

    def test_structured_primary_action_is_enough_for_motion_handoff(self):
        p=self.prepare();_,image=self.image_return('structured')
        p=self.studio.set_policy(p['id'],{'visual_direction':False},self.p['revision'])
        shots=copy.deepcopy(p['shots']);shots[0]['motion_prompt']='';shots[0]['direction']['action']['primary_action']='Turns toward the north window'
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        task=self.studio.claim_next(p['id'],'agent','structured-action')
        self.assertIsNotNone(task.get('handoff'),'Structured primary action should compile without duplicate base text')
        self.assertIn('Turns toward the north window',task['handoff']['prompt'])

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

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_motion_reference_requires_real_video_and_exports_it(self):
        from studio.preflight import preflight, references_for
        p=self.prepare()
        image=self.studio.inbox/'still.png';Image.new('RGB',(32,18),'orange').save(image)
        p=self.studio.import_reference(p['id'],str(image),'Still',p['revision'],'user')
        still=p['assets'][-1]
        shots=copy.deepcopy(p['shots'])
        shots[0]['direction'].update(generation_mode='motion_control',references=[{'slot':'motion','asset_id':still['id'],'role':'motion','version':1}])
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        self.assertGreater(preflight(p)['errors'],0,'A still cannot certify a motion source')
        file=self.studio.inbox/'motion.mp4'
        subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=orange:s=32x18:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(file)],capture_output=True,check=True)
        p=self.studio.import_reference(p['id'],str(file),'Motion source',p['revision'],'user',kind='video')
        motion=p['assets'][-1]
        shots=copy.deepcopy(p['shots']);shots[0]['direction']['references']=[{'slot':'motion','asset_id':motion['id'],'role':'motion','version':1,'notes':'Match initial pose and full body framing'}]
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        self.assertEqual(preflight(p)['errors'],0)
        self.assertFalse(references_for(p,p['shots'][0],'image'))
        self.assertEqual(references_for(p,p['shots'][0],'video')[0]['kind'],'video')
        self.p=p;self.image_return('motion-target')
        p=self.studio.set_policy(p['id'],{'visual_direction':False},self.p['revision'])
        handoff=self.studio.claim_next(p['id'],'agent','motion-source-handoff')['handoff']
        self.assertTrue(any(r['id']==motion['id'] and r['kind']=='video' for r in handoff['references']))
        bundle=self.studio.export_handoff(p['id'])
        entry=next(r for r in bundle['manifest']['references'] if r['asset_id']==motion['id'])
        with zipfile.ZipFile(bundle['path']) as archive:self.assertIn(entry['file'],archive.namelist())

    def test_export_includes_explicitly_bound_unselected_generated_image(self):
        p=self.prepare();_,result=self.image_return('bound')
        p=self.p
        alternate=copy.deepcopy(result['asset']);alternate['id']='unselected-image'
        p=self.studio.mutate(p['id'],p['revision'],lambda current:current['assets'].append(alternate))
        shots=copy.deepcopy(p['shots']);shots.append({'title':'Second','image_prompt':'Same traveler','motion_prompt':'Still','direction':{'references':[{'slot':'identity','asset_id':alternate['id'],'role':'character','version':1}]}})
        p=self.studio.update_shots(p['id'],shots,p['revision'],'agent')
        bundle=self.studio.export_handoff(p['id'])
        self.assertEqual(bundle['manifest']['preflight']['errors'],0)
        entry=next((r for r in bundle['manifest']['references'] if r['asset_id']==alternate['id']),None)
        self.assertIsNotNone(entry,'Explicit binding must have a portable file mapping')
        with zipfile.ZipFile(bundle['path']) as archive:self.assertIn(entry['file'],archive.namelist())

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
        result=return_fixture(self.studio, task['job']['id'],str(file),'agent')
        p=self.studio.get_project(p['id'])
        self.assertTrue(hasattr(self.studio,'extract_continuation'),'Missing real frame extraction')
        p=self.studio.extract_continuation(p['id'],result['asset']['id'],p['revision'],'agent')
        frame=next(a for a in p['assets'] if a.get('source_video')==result['asset']['id'])
        with Image.open(frame['path']) as img:self.assertEqual(img.size,(32,18))
        handoff=self.studio.repair_handoff(p['id'],frame['id'],'Fix one corner','',p['revision'],'agent')
        self.assertEqual(handoff['original']['id'],frame['id'])
        self.assertIn('preserve',handoff)

        # A retained compatible alternate take must invalidate bound derived frames,
        # even when the following shot has no explicit continuity_from link.
        alternate=copy.deepcopy(result['asset']);alternate['id']='alternate-synthetic-take'
        p=self.studio.mutate(p['id'],p['revision'],lambda current:current['assets'].append(alternate))
        first=p['shots'][0]
        second={'title':'Following shot','image_prompt':'Traveler continues','motion_prompt':'One step',
                'direction':{'references':[{'slot':'start','asset_id':frame['id'],'version':1,'role':'start_frame'}]}}
        p=self.studio.update_shots(p['id'],[first,second],p['revision'],'agent')
        pending=self.studio.claim_next(p['id'],'agent','dependent-image')
        p=self.studio.get_project(p['id'])
        p=self.studio.select_take(p['id'],alternate['id'],p['revision'],'user')
        self.assertTrue(next(a for a in p['assets'] if a['id']==frame['id'])['stale'])
        self.assertEqual(next(j for j in p['jobs'] if j['id']==pending['job']['id'])['status'],'superseded')
