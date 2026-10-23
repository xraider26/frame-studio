from workflow_fixtures import CREATOR_SETTINGS, creator_ready
import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from studio.workflow import Studio
from studio.store import StudioError
from studio.creative import effective_direction
from studio.preflight import preflight


class BatchIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        r=Path(self.temp.name);self.s=Studio(r/'db',r/'media',r/'inbox')
        self.source=self.s.create_project('Canonical cast','ai-film')
        file=self.s.inbox/'portrait.png';Image.new('RGB',(40,40),'orange').save(file)
        self.source=self.s.import_reference(self.source['id'],str(file),'Hero portrait',self.source['revision'],'user')
        self.source=self.s.update_production(self.source['id'],{'bible':[{'id':'hero','kind':'character','name':'Traveler','identity':'Round glasses and copper coat','asset_ids':[self.source['assets'][0]['id']]}]},self.source['revision'],'user')

    def test_canonical_real_files_and_bindings_are_shared_and_definitions_locked(self):
        self.assertTrue(hasattr(self.s,'sync_batch_identity'),'Shared identity synchronization is missing')
        b=self.s.create_batch('Episode','One idea','episodes','ai-film',2,'identity','user')
        b=self.s.sync_batch_identity(b['id'],self.source['id'],b['revision'],self.source['revision'])
        p=self.s.get(b['project_ids'][0]);other=self.s.get(b['project_ids'][1])
        entity=p['production']['bible'][0]
        self.assertEqual(entity['identity'],'Round glasses and copper coat')
        refs=effective_direction(p,p['shots'][0])['references']
        self.assertEqual(refs[0]['entity_id'],'hero')
        file=next(a for a in p['assets'] if a['id']==refs[0]['asset_id'])
        self.assertTrue(Path(file['path']).is_file())
        self.assertNotEqual(file['id'],other['assets'][0]['id'])
        self.assertEqual(preflight(p)['errors'],0)
        changed=copy.deepcopy(p['production']);changed['bible'][0]['identity']='Different actor'
        with self.assertRaises(StudioError):self.s.update_production(p['id'],changed,p['revision'],'agent')
        allowed={'bible':p['production']['bible']+[{'id':'guest','kind':'character','name':'Guest'}]}
        self.s.update_production(p['id'],allowed,p['revision'],'agent')

    def test_applying_a_story_recipe_preserves_the_batch_canonical_identity(self):
        self.assertTrue(hasattr(self.s,'sync_batch_identity'))
        b=self.s.create_batch('Batch','Idea','episodes','ai-film',1,'recipe-lock','user')
        b=self.s.sync_batch_identity(b['id'],self.source['id'],b['revision'],self.source['revision'])
        recipe_source=self.s.create_project('Other cast','ai-film')
        recipe_source=self.s.update_production(recipe_source['id'],{'bible':[{'id':'hero','kind':'character','name':'Wrong hero','identity':'Different face'}]},recipe_source['revision'],'user')
        saved=self.s.save_project_template(recipe_source['id'],'Other story','',['story'],recipe_source['revision'])
        p=self.s.get(b['project_ids'][0])
        p=self.s.apply_project_template(p['id'],saved['id'],['story'],p['revision'],saved['revision'],'agent')
        self.assertEqual(p['production']['bible'][0]['identity'],'Round glasses and copper coat')

    def test_sync_new_version_reopens_dependent_output_and_preserves_original_files(self):
        self.assertTrue(hasattr(self.s,'sync_batch_identity'))
        b=self.s.create_batch('Episode','Idea','episodes','ai-film',1,'change','user')
        b=self.s.sync_batch_identity(b['id'],self.source['id'],b['revision'],self.source['revision'])
        p=self.s.get(b['project_ids'][0]);old_file=p['assets'][0]['path']
        p=creator_ready(self.s,p)
        for step in ['brief','script']:
            p=self.s.set_policy(p['id'],{step:False},p['revision'])
            p=self.s.complete_step(p['id'],step,{'text':'Actual document'},p['revision'],'agent')
        p=self.s.update_shots(p['id'],[{**p['shots'][0],'image_prompt':'Hero close portrait','motion_prompt':'Turns'}],p['revision'],'agent')
        job=self.s.claim_next(p['id'],'agent','pending')['job']
        self.source=self.s.update_production(self.source['id'],{'bible':[{**self.source['production']['bible'][0],'wardrobe':'Blue scarf'}]},self.source['revision'],'user')
        b=self.s.sync_batch_identity(b['id'],self.source['id'],b['revision'],self.source['revision'])
        p=self.s.get(p['id'])
        self.assertEqual(p['shared_identity']['version'],2)
        self.assertEqual(next(j for j in p['jobs'] if j['id']==job['id'])['status'],'superseded')
        self.assertTrue(Path(old_file).is_file())
        self.assertEqual(p['production']['bible'][0]['wardrobe'],'Blue scarf')

    def test_named_visible_cast_selects_only_relevant_canonical_references(self):
        self.assertTrue(hasattr(self.s,'sync_batch_identity'))
        guest={**self.source['production']['bible'][0],'id':'guest','name':'Guest'}
        self.source=self.s.update_production(self.source['id'],{'bible':self.source['production']['bible']+[guest]},self.source['revision'],'user')
        b=self.s.create_batch('Cast','Idea','episodes','ai-film',1,'cast','user',identity_source_project_id=self.source['id'],source_revision=self.source['revision'])
        p=self.s.get(b['project_ids'][0]);shots=copy.deepcopy(p['shots'])
        shots[0]['direction']['action']['visible_entities']=['hero']
        p=self.s.update_shots(p['id'],shots,p['revision'],'agent')
        refs=effective_direction(p,p['shots'][0])['references']
        self.assertEqual({r['entity_id'] for r in refs},{'hero'})

    def test_guest_only_shot_does_not_fallback_to_offscreen_canonical_character(self):
        from studio.preflight import references_for
        self.assertTrue(hasattr(self.s,'sync_batch_identity'))
        b=self.s.create_batch('Guest','Idea','episodes','ai-film',1,'guest-only','user',identity_source_project_id=self.source['id'],source_revision=self.source['revision'])
        p=self.s.get(b['project_ids'][0])
        p=self.s.update_production(p['id'],{'bible':p['production']['bible']+[{'id':'guest','kind':'character','name':'Unrelated guest'}]},p['revision'],'agent')
        shots=copy.deepcopy(p['shots']);shots[0]['direction']['action']['visible_entities']=['guest']
        p=self.s.update_shots(p['id'],shots,p['revision'],'agent')
        self.assertFalse(effective_direction(p,p['shots'][0])['references'])
        self.assertFalse(references_for(p,p['shots'][0],'image'),'An offscreen canonical reference must not return through legacy fallback')
