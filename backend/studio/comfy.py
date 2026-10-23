"""Explicit ComfyUI API workflow mapping and execution; no inferred model settings."""
import asyncio
import copy
import json
import uuid
from pathlib import Path, PurePosixPath

MAX_DOWNLOAD_BYTES = 500_000_000


class ComfyError(ValueError):
    """Actionable connector failure safe to report without remote response bodies."""


def targets(config):
    bindings = config['bindings']
    return [bindings[k] for k in ['positive', 'negative', 'seed'] if k in bindings] + bindings.get('references', [])


def validate_config(value):
    if not isinstance(value, dict) or set(value) - {'kind', 'workflow', 'bindings', 'output_node'}:
        raise ComfyError('ComfyUI config needs kind, workflow, bindings and output_node.')
    wf, b = value.get('workflow'), value.get('bindings')
    if value.get('kind') not in ['image', 'video']:
        raise ComfyError('Choose image or video for this ComfyUI workflow.')
    if not isinstance(wf, dict) or not wf or 'nodes' in wf or len(wf) > 2000:
        raise ComfyError('Import ComfyUI API-format JSON (Export API), not the canvas nodes/links format.')
    if len(json.dumps(value)) > 2_000_000:
        raise ComfyError('ComfyUI configuration exceeds 2 MB.')
    for node, data in wf.items():
        if not isinstance(node, str) or not isinstance(data, dict) or not isinstance(data.get('class_type'), str) or not isinstance(data.get('inputs'), dict):
            raise ComfyError('Every API workflow node needs class_type and inputs.')
        for v in data['inputs'].values():
            if isinstance(v, list) and (len(v) != 2 or str(v[0]) not in wf or type(v[1]) is not int or v[1] < 0):
                raise ComfyError('Workflow links must identify an existing node and nonnegative output index.')
    if not isinstance(b, dict) or 'positive' not in b or set(b) - {'positive', 'negative', 'seed', 'references'} or not isinstance(b.get('references', []), list):
        raise ComfyError('Map a positive prompt plus optional negative, seed and references.')
    used, slots = set(), set()
    for t in targets(value):
        if not isinstance(t, dict) or set(t) - {'node', 'input', 'slot', 'value'}:
            raise ComfyError('Bindings use node/input, a reference slot or an explicit seed value.')
        n, key = t.get('node'), t.get('input')
        if not isinstance(n, str) or not isinstance(key, str) or n not in wf or key not in wf[n]['inputs'] or isinstance(wf[n]['inputs'][key], (list, dict)):
            raise ComfyError('Bind an existing literal workflow input; linked inputs cannot be overwritten.')
        if (n, key) in used:
            raise ComfyError('Two bindings cannot overwrite the same workflow input.')
        used.add((n, key))
    for t in b.get('references', []):
        slot = t.get('slot')
        if not isinstance(slot, str) or not slot or slot in slots:
            raise ComfyError('Reference bindings need distinct nonempty slots.')
        slots.add(slot)
    if 'seed' in b and (type(b['seed'].get('value')) is not int or not 0 <= b['seed']['value'] <= 2**64-1):
        raise ComfyError('A seed mapping needs an explicit nonnegative integer value; omit it to preserve the workflow seed.')
    if not isinstance(value.get('output_node'), str) or value['output_node'] not in wf:
        raise ComfyError('Choose an existing output node ID; preview nodes are not selected automatically.')
    return copy.deepcopy(value)


def build_workflow(config, handoff, uploaded):
    config = validate_config(config)
    if handoff['kind'] != config['kind']:
        raise ComfyError('The ComfyUI workflow media kind does not match this job.')
    refs = handoff.get('references', [])
    slots = [r['slot'] for r in refs]
    mapped = [t['slot'] for t in config['bindings'].get('references', [])]
    if len(slots) != len(set(slots)) or set(slots) != set(mapped) or set(uploaded) != set(mapped):
        raise ComfyError('Map every handoff reference slot exactly once; remove unused workflow reference inputs or bind them explicitly.')
    if (handoff.get('image_requirements') or {}).get('mode') == 'edit' and (not refs or not any(r['role'] in ['character','location','prop','style','start_frame'] for r in handoff.get('effective_direction', {}).get('references', []))):
        raise ComfyError('Image editing needs a bound source reference.')
    wf, b = config['workflow'], config['bindings']
    for key, value in [('positive', handoff['prompt']), ('negative', handoff.get('negative_prompt', '')), ('seed', b.get('seed', {}).get('value'))]:
        if key in b:
            wf[b[key]['node']]['inputs'][b[key]['input']] = value
    if handoff.get('negative_prompt') and 'negative' not in b:
        raise ComfyError('This prompt has exclusions. Map a negative input or revise the profile/exclusions explicitly.')
    for t in b.get('references', []):
        wf[t['node']]['inputs'][t['input']] = uploaded[t['slot']]
    return wf


def validate_installed(config, schemas):
    config = validate_config(config)
    mapped = {(t['node'], t['input']) for t in targets(config)}
    for node, data in config['workflow'].items():
        schema = schemas.get(data['class_type'])
        if not isinstance(schema, dict):
            raise ComfyError(f'ComfyUI is missing node class {data["class_type"]}. Install the workflow requirements yourself before execution.')
        spec = schema.get('input', {})
        inputs = {**spec.get('required', {}), **spec.get('optional', {})}
        if set(spec.get('required', {})) - set(data['inputs']):
            raise ComfyError(f'Node {node} is missing inputs required by this installed ComfyUI version. Re-export its API workflow.')
        for key, value in data['inputs'].items():
            if key not in inputs:
                raise ComfyError(f'Node {node} has an input unavailable in the installed node schema.')
            descriptor = inputs[key]
            if isinstance(value, list):
                continue
            if descriptor and isinstance(descriptor[0], list) and (node, key) not in mapped and value not in descriptor[0]:
                raise ComfyError(f'Node {node} selects an unavailable model or option for {key}. Check the installed files and workflow.')
            # Never let an unmapped LoadImage read a stale arbitrary local file.
            upload_spec = descriptor[1] if len(descriptor)>1 and isinstance(descriptor[1],dict) else {}
            upload_input = any(upload_spec.get(flag) for flag in ['image_upload','video_upload','audio_upload'])
            known_file_input = data['class_type'] in ['LoadImage', 'LoadImageMask', 'LoadVideo', 'VHS_LoadVideo', 'VHS_LoadVideoPath', 'LoadAudio'] and key in ['image', 'video', 'audio', 'file']
            if (upload_input or known_file_input) and (node, key) not in mapped:
                raise ComfyError(f'Node {node} needs an explicit reference mapping; implicit workflow file inputs are not allowed.')
    output_schema = schemas[config['workflow'][config['output_node']]['class_type']]
    if output_schema.get('output_node') is not True:
        raise ComfyError('The selected output node is not an installed output node.')
    return {'status': 'validated', 'node_count': len(config['workflow']), 'kind': config['kind'], 'output_node': config['output_node']}


async def execute_comfy(client, config, handoff, media_root, inbox, record_prompt, *, poll_interval=2, attempts=1800, before_submit=None):
    config = validate_config(config)
    refs = handoff.get('references', [])
    # Check mappings before making uploads or queueing work.
    build_workflow(config, handoff, {r['slot']: 'pending-upload' for r in refs})
    schemas = await client.get('/object_info'); schemas.raise_for_status()
    validate_installed(config, schemas.json())
    uploaded = {}
    for ref in refs:
        path = Path(ref.get('path', '')).resolve()
        if not path.is_relative_to(Path(media_root).resolve()) or not path.is_file() or path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp'] or path.stat().st_size > 50_000_000:
            raise ComfyError('ComfyUI references must be existing project images within media storage, at most 50 MB. Video/audio reference upload is not supported in this first connector.')
        # Unique uploaded names prevent overwriting another workflow's source.
        with path.open('rb') as stream:
            response = await client.post('/upload/image', files={'image': ('orchestra-' + uuid.uuid4().hex + path.suffix, stream, ref.get('mime', 'image/png'))}, data={'overwrite': 'false'})
        response.raise_for_status()
        data = response.json()
        name, subfolder = data.get('name'), data.get('subfolder', '')
        if not safe_relative(name) or (subfolder and not safe_relative(subfolder)):
            raise ComfyError('ComfyUI returned an invalid uploaded reference name.')
        uploaded[ref['slot']] = '/'.join(p for p in [subfolder, name] if p)
    workflow = build_workflow(config, handoff, uploaded)
    if before_submit: before_submit()
    response = await client.post('/prompt', json={'prompt': workflow, 'client_id': 'orchestra-' + uuid.uuid4().hex})
    response.raise_for_status()
    data = response.json()
    prompt_id = data.get('prompt_id')
    if data.get('node_errors') or not isinstance(prompt_id, str) or not prompt_id or len(prompt_id) > 200 or not all(c.isalnum() or c in '-_' for c in prompt_id):
        raise ComfyError('ComfyUI rejected the workflow. Check node inputs/models in ComfyUI before retrying.')
    record_prompt(prompt_id)
    for _ in range(attempts):
        response = await client.get('/history/' + prompt_id); response.raise_for_status()
        result = response.json().get(prompt_id)
        if result:
            status = result.get('status', {})
            if status.get('status_str') == 'error' or any(m[0] in ['execution_error', 'execution_interrupted'] for m in status.get('messages', []) if isinstance(m, list) and m):
                raise ComfyError('ComfyUI execution failed or was interrupted. Inspect the remote prompt history; no output was accepted.')
            if status.get('completed') is True:
                output = result.get('outputs', {}).get(config['output_node'], {})
                suffixes = {'.png', '.jpg', '.jpeg', '.webp'} if handoff['kind'] == 'image' else {'.mp4'}
                files = [f for key in ['images', 'videos', 'gifs'] for f in output.get(key, []) if isinstance(f, dict) and Path(f.get('filename', '')).suffix.lower() in suffixes and f.get('type', 'output') == 'output']
                if len(files) != 1:
                    raise ComfyError('The mapped output node must return exactly one supported image or MP4. Choose an unambiguous output and batch size.')
                file = files[0]
                if not safe_relative(file['filename']) or (file.get('subfolder') and not safe_relative(file['subfolder'])):
                    raise ComfyError('ComfyUI returned an invalid output filename.')
                path = Path(inbox) / (uuid.uuid4().hex + Path(file['filename']).suffix.lower())
                path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    async with client.stream('GET', '/view', params={'filename': file['filename'], 'subfolder': file.get('subfolder', ''), 'type': 'output'}) as download:
                        download.raise_for_status()
                        total = 0
                        with path.open('wb') as stream:
                            async for chunk in download.aiter_bytes():
                                total += len(chunk)
                                if total > MAX_DOWNLOAD_BYTES:
                                    raise ComfyError('ComfyUI output exceeds the 500 MB download limit.')
                                stream.write(chunk)
                    return path
                except BaseException:
                    path.unlink(missing_ok=True)
                    raise
        await asyncio.sleep(poll_interval)
    raise ComfyError('ComfyUI timed out. The remote prompt may still run; inspect its saved prompt ID before retrying.')


def safe_relative(value):
    return isinstance(value, str) and bool(value) and '\\' not in value and ':' not in value and not PurePosixPath(value).is_absolute() and '..' not in PurePosixPath(value).parts
