import copy, tempfile, unittest
from pathlib import Path
from studio.workflow import Studio
from studio.store import StudioError
from studio.recipes import recipe_catalog

class TemplatesSequencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); self.studio=Studio(root/'db',root/'media',root/'inbox')
    def test_image_recipes_have_still_only_contract(self):
        recipes={r['id']:r for r in recipe_catalog(detail="full", include_provenance=True)}
        self.assertIn('image-product', recipes)
        r=recipes['image-product']; self.assertEqual(r['output_type'],'image')
        self.assertEqual(set(r['stages']),{'brief','script','visual_direction','final_review'})
        self.assertEqual(r['video_checks'],[])
        p=self.studio.create_project('Product','image-product',output_type='image')
        self.assertEqual(len(p['shots']),1)
        self.assertEqual(self.studio.create_project('Legacy call','custom',output_type='image')['template_id'],'image-custom')
        with self.assertRaises(StudioError): self.studio.create_project('Mismatch','podcast',output_type='image')
    def test_saved_image_kind_cannot_replace_video_story(self):
        p=self.studio.create_project('Image','custom',output_type='image')
        t=self.studio.save_project_template(p['id'],'Still','',['settings','story'],p['revision'])
        self.assertEqual(t['output_type'],'image')
        v=self.studio.create_project('Video','custom')
        with self.assertRaises(StudioError): self.studio.apply_project_template(v['id'],t['id'],['story'],v['revision'],t['revision'],'user')
        self.studio.apply_project_template(v['id'],t['id'],['settings'],v['revision'],t['revision'],'user')
    def test_sequence_replaces_atomically_and_preserves_policy_and_audio_links(self):
        p=self.studio.create_project('Creator','explainer')
        p=self.studio.update_settings(p['id'],{'duration_seconds':95},p['revision'],'user')
        old=copy.deepcopy(p)
        preview=self.studio.preview_sequence(p['id'],'creator-explainer')
        self.assertFalse(preview['replacement_required'])
        p=self.studio.apply_sequence(p['id'],'creator-explainer',p['revision'],False,'user')
        self.assertEqual(p['production']['story']['sequence_id'],'creator-explainer')
        self.assertEqual(p['settings'],old['settings']); self.assertEqual(p['approval_policy'],old['approval_policy'])
        self.assertAlmostEqual(sum(s['edit_duration_seconds'] for s in p['shots']),95)
        self.assertTrue(all(1<=s['duration_seconds']<=30 for s in p['shots']))
        ids={s['id'] for s in p['shots']}
        for shot in p['shots']:
            source=shot['direction']['editorial']['audio_source_shot_id']
            self.assertTrue(not source or source in ids)
        self.assertEqual(p['jobs'],[])
        with self.assertRaises(StudioError): self.studio.apply_sequence(p['id'],'montage',p['revision'],False,'user')
        with self.assertRaises(StudioError): self.studio.apply_sequence(p['id'],'montage',p['revision'],True,'agent:test')
        image=self.studio.create_project('Image','custom',output_type='image')
        with self.assertRaises(StudioError): self.studio.apply_sequence(image['id'],'montage',image['revision'],True,'user')
    def test_sequence_rejects_too_short_without_changes(self):
        p=self.studio.create_project('Short','custom',settings={'duration_seconds':2})
        with self.assertRaises(StudioError): self.studio.apply_sequence(p['id'],'podcast-conversation',p['revision'],False,'user')
        self.assertEqual(self.studio.get(p['id'])['revision'],p['revision'])

    def test_sequence_retains_media_and_exports_editorial_context(self):
        p=self.studio.create_project('Authored','custom')
        def authored(q):
            q['assets']=[{'id':'old','kind':'video','shot_id':q['shots'][0]['id'],'stale':False}]
            q['jobs']=[{'id':'pending','status':'awaiting_external_output'}]
        p=self.studio.mutate(p['id'],p['revision'],authored)
        self.assertTrue(self.studio.preview_sequence(p['id'],'montage')['replacement_required'])
        p=self.studio.apply_sequence(p['id'],'montage',p['revision'],True,'user')
        self.assertTrue(p['assets'][0]['stale']); self.assertEqual(p['jobs'][0]['status'],'superseded')
        self.assertEqual(p['epoch'],2)
        manifest=self.studio.export_handoff(p['id'])['manifest']
        self.assertEqual(manifest['sequence_context']['id'],'montage')
        handoff=self.studio.editor_handoff(p['id'])
        self.assertIn('L-cuts',handoff['instructions'])
        self.assertEqual(handoff['sequence_context']['id'],'montage')

    def test_authored_camera_alone_requires_confirmation(self):
        p=self.studio.create_project('Authored','custom')
        p=self.studio.mutate(p['id'],p['revision'],lambda q:q['shots'][0]['direction']['camera'].update(lens='My intentional 65mm'))
        self.assertTrue(self.studio.preview_sequence(p['id'],'montage')['replacement_required'])
        with self.assertRaises(StudioError): self.studio.apply_sequence(p['id'],'montage',p['revision'],False,'user')

    def test_native_image_context_keeps_tailored_composition(self):
        p=self.studio.create_project('Product','image-product',output_type='image')
        from studio.recipes import recipe_context
        r=recipe_context(p)
        self.assertIn('Product silhouette and material detail',r['planning'])
        self.assertEqual(r['final_checks'],r['image_checks'])

    def test_api_agent_can_read_catalog_but_cannot_apply_sequence(self):
        from fastapi.testclient import TestClient
        from studio.api import create_app
        app=create_app(Path(self.tmp.name)/'api','agent','human')
        with TestClient(app) as client:
            def command(op,args=None,token='agent'):
                return client.post('/studio/v1/command',json={'operation':op,'arguments':args or {}},headers={'Authorization':'Bearer '+token})
            catalog=command('sequence_catalog').json()
            self.assertEqual(len(catalog['sequences']),7)
            p=command('create_project',{'name':'API','template_id':'custom'}).json()
            args={'project_id':p['id'],'sequence_id':'creator-explainer','expected_revision':p['revision']}
            self.assertEqual(command('apply_sequence',args).status_code,403)
            self.assertEqual(command('apply_sequence',args,'human').status_code,200)

    def test_editorial_source_is_validated_and_saved_story_remaps_links(self):
        from studio.preflight import preflight
        p=self.studio.create_project('Links','custom')
        p=self.studio.apply_sequence(p['id'],'creator-explainer',p['revision'],False,'user')
        t=self.studio.save_project_template(p['id'],'Coverage','',['story'],p['revision'])
        clone=self.studio.create_project('Clone',t['id'])
        ids={s['id'] for s in clone['shots']}
        self.assertTrue(all(not s['direction']['editorial']['audio_source_shot_id'] or s['direction']['editorial']['audio_source_shot_id'] in ids for s in clone['shots']))
        p['shots'][1]['direction']['editorial']['audio_source_shot_id']='missing'
        self.assertTrue(any(e['rule']=='editorial_source' for e in preflight(p)['issues']))

    def test_old_saved_template_kind_inferred_and_legacy_project_remains_readable(self):
        import json
        p=self.studio.create_project('Legacy image','custom',output_type='image')
        def legacy(q):
            q['template_id']='podcast'
            q['production']['recipe']={'id':'podcast','version':1}
        p=self.studio.mutate(p['id'],p['revision'],legacy)
        self.assertEqual(self.studio.get_project(p['id'])['output_type'],'image')
        t=self.studio.save_project_template(p['id'],'Legacy image setup','',['settings','story'],p['revision'])
        with self.studio.connect() as conn:
            raw=self.studio.get_saved_template(t['id']);raw.pop('output_type')
            conn.execute('UPDATE studio_templates SET payload=? WHERE id=?',(json.dumps(raw),t['id']))
        self.assertEqual(self.studio.get_saved_template(t['id'])['output_type'],'image')
        clone=self.studio.create_project('Legacy clone',t['id'],output_type='image')
        self.assertEqual(clone['output_type'],'image')
        duplicate=self.studio.duplicate_project(p['id'],'Duplicate','user')
        self.assertTrue(self.studio.get_project(duplicate['id'])['recipe_context']['active'])


    def test_authored_timing_requires_confirmation(self):
        p=self.studio.create_project('Timed','custom')
        def trim(q): q['shots'][0]['edit_in_seconds']=1
        p=self.studio.mutate(p['id'],p['revision'],trim)
        self.assertTrue(self.studio.preview_sequence(p['id'],'montage')['replacement_required'])

    def test_image_template_aspect_can_be_saved_back_through_settings(self):
        p=self.studio.create_project('Portrait','image-portrait',output_type='image')
        p=self.studio.update_settings(p['id'],{'aspect_ratio':p['settings']['aspect_ratio']},p['revision'],'user')
        self.assertEqual(p['settings']['aspect_ratio'],'4:5')

    def test_story_restore_clears_retained_default_audio_source(self):
        from studio.preflight import preflight
        source=self.studio.create_project('Source','custom')
        t=self.studio.save_project_template(source['id'],'Story','',['story'],source['revision'])
        target=self.studio.create_project('Target','custom')
        target=self.studio.mutate(target['id'],target['revision'],lambda p:p['production']['defaults']['editorial'].update(audio_source_shot_id=p['shots'][0]['id']))
        target=self.studio.apply_project_template(target['id'],t['id'],['story'],target['revision'],t['revision'],'user')
        self.assertEqual(target['production']['defaults']['editorial']['audio_source_shot_id'],'')
        self.assertFalse(any(e['rule']=='editorial_source' for e in preflight(target)['issues']))
