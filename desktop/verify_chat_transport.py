"""Synthetic workflow assertions through the real frozen MCP bridge; no model calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import uuid
from PIL import Image


async def verify_chat_transport(client):
    async def call(tool_name, **arguments):
        response = await client.call_tool(tool_name, arguments)
        assert not response.isError, (tool_name, response.content)
        payload = response.structuredContent
        if payload is None:
            payload = json.loads(next(c.text for c in response.content if c.type == 'text'))
        return payload.get('result', payload) if isinstance(payload, dict) and set(payload) == {'result'} else payload

    selection = {'executor':'agent_builtin','tool_name':'Synthetic local fixture, no AI call','profile':'general_image',
                 'model':None,'model_version_status':'managed','connection_id':None,'selection_source':'creator_statement',
                 'source_text':'Synthetic transport-test instruction, not a creator artistic approval.'}
    await call('start_project_setup', output_type='image')
    p = await call('create_project', name='Synthetic 0.3.2 chat transport '+uuid.uuid4().hex[:8], template_id='image-custom', output_type='image',
                   generation_setup={'version':1,'image':selection,'video':None}, settings={'creative_intake':{
                       'vision':'Flat orange software fixture, then flat blue software fixture','art_style':'Flat color','purpose':'Protocol regression only'}})
    project_id = p['id']

    async def current():
        return await call('get_project', project_id=project_id)

    async def acknowledge():
        contract = await call('get_workflow_contract', project_id=project_id)
        await call('acknowledge_workflow_contract', project_id=project_id, contract_version=contract['contract_version'], expected_revision=contract['revision'])
        return await current()

    p = await acknowledge()
    for step in ['brief','script']:
        p = await call('complete_step', project_id=project_id, expected_revision=p['revision'], step=step, output={'text':'Synthetic flat-color transport fixture; not an artistic production.'})
    p = await call('update_shots', project_id=project_id, expected_revision=p['revision'], shots=[{'title':'Orange fixture','image_prompt':'An individual flat orange image, no text.'}])

    working = Path(tempfile.mkdtemp(prefix='MCP 032 fixture ', dir=Path(__file__).resolve().parents[1]/'.superpowers'))

    async def submit(request_id, color):
        p = await current()
        claimed = await call('claim_generation', project_id=project_id, expected_revision=p['revision'], request_id=request_id)
        assert claimed['job'] and not claimed.get('already_claimed'), claimed
        h = claimed['handoff']
        local = h.get('local_reference_files', [])
        if h['references']:
            assert len(local) == len(h['references'])
            source = Path(local[0]['path'])
            assert source.is_file()
            assert hashlib.sha256(source.read_bytes()).hexdigest() == local[0]['sha256']
            assert str(source) != h['references'][0]['path'], 'Reference must cross into the client cache'
            with Image.open(source) as image:
                fixture = image.convert('RGB')
                fixture.paste(color, (0,0,fixture.width,fixture.height))
        else:
            fixture = Image.new('RGB',(32,18),color)
        file = working/(request_id+'.png')
        fixture.save(file)
        native = {'fixture':True, 'operation':'flat-color reference recolor', 'referenced_image_paths':[f['path'] for f in local]}
        execution = await call('record_generation_execution', job_id=claimed['job']['id'], expected_revision=h['source_revision'], execution={
            'tool':'synthetic-pillow-fixture','prompt':h['prompt'],'negative_prompt':h['negative_prompt'],
            'references':h['execution_contract']['references'],'arguments':native})
        assert execution['validation']['state'] == 'match', execution
        returned = await call('return_generation', job_id=claimed['job']['id'], output_path=str(file))
        again = await call('return_generation', job_id=claimed['job']['id'], output_path=str(file))
        assert again['asset']['id'] == returned['asset']['id']
        p = await current()
        # Actual controlled fixture pixels and dimensions are inspected here;
        # this asserts software transport only, not generated artistic quality.
        with Image.open(file) as check:
            assert check.size == (32,18) and check.getpixel((0,0)) == Image.new('RGB',(1,1),color).getpixel((0,0))
        await call('record_take_review', project_id=project_id, expected_revision=p['revision'], asset_id=returned['asset']['id'], review={
            'inspected':['image'],'criteria':{text:True for text in returned['next_action']['criteria']},
            'notes':'Controlled synthetic flat-color fixture pixels and dimensions inspected in the test harness; no artistic/media-generation validation.', 'defect':''})
        return returned['asset']

    first = await submit('orange-'+uuid.uuid4().hex[:8], 'orange')
    p = await current()
    assert p['next_action']['action'] == 'await_calibration_approval'
    decision = dict(project_id=project_id, expected_revision=p['revision'], request_id='fixture-approval-'+uuid.uuid4().hex,
                    user_instruction='Synthetic test instruction: accept this flat orange fixture only for protocol verification.',
                    operation='review_calibration', arguments={'asset_id':first['id'],'approve':True})
    approved = await call('creator_decision', **decision)
    duplicate = await call('creator_decision', **decision)
    assert duplicate['decision']['request_id'] == approved['decision']['request_id']
    p = await current()
    assert p['calibration_state']['status'] == 'approved'
    shots = p['shots']+[{'title':'Blue fixture','image_prompt':'An individual flat blue software fixture, no text.', 'direction':{
        'art':{'palette':'Blue','materials':'Flat color'},'lighting':{'world_source':'Synthetic even light'},
        'references':[{'slot':'approved_style','asset_id':first['id'],'version':first['version'],'role':'style'}]}}]
    await call('update_shots', project_id=project_id, expected_revision=p['revision'], shots=shots)
    second = await submit('blue-'+uuid.uuid4().hex[:8], 'blue')
    p = await current()
    assert p['calibration_state']['status'] == 'approved', p['calibration_state']
    assert p['next_action']['action'] != 'await_calibration_approval', p['next_action']
    modified = await call('creator_decision', project_id=project_id, expected_revision=p['revision'], request_id='fixture-revision-'+uuid.uuid4().hex,
                          user_instruction='Synthetic instruction: revise the blue fixture.', operation='request_revision',
                          arguments={'shot_id':second['shot_id'],'asset_id':second['id'],'kind':'image'})
    assert modified['decision']['authority'] == 'user_instruction_relayed'
    assert modified['next_action']['action'] == 'generate', modified
    return {'chat_decision':'passed','owned_job_upload':'passed','reference_staging_and_digest':'passed','shared_calibration_scene_variation':'passed','project_id':project_id}
