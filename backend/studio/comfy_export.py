"""Portable mapped workflows using the same compiler as direct execution."""
import json
import uuid
import zipfile
from pathlib import Path

from .comfy import build_workflow, validate_config, ComfyError
from .generators import prompt_for
from .preflight import references_for
from .store import StudioError


def export_comfy(studio, providers, project_id, connection_id):
    project = studio.get_project(project_id)
    connection = providers.connections.get(connection_id)
    if not connection or connection.get('adapter') != 'comfyui':
        raise StudioError('invalid_connection', 'Choose a saved ComfyUI connection.')
    config = validate_config(connection['comfy'])
    kind = config['kind']
    if project.get('output_type') == 'image' and kind != 'image':
        raise StudioError('wrong_workflow_kind', 'Image projects require an image workflow.')
    files, workflows, manifest = {}, {}, {'project_id': project_id, 'source_revision': project['revision'], 'kind': kind, 'shots': [], 'execution_authorized': False}
    try:
        for shot in project['shots']:
            prepared = prompt_for(project, shot, kind)
            refs = references_for(project, shot, kind)
            names, ref_manifest = {}, []
            for ref in refs:
                path = Path(ref['path']).resolve()
                if not path.is_relative_to(studio.media_root) or not path.is_file() or path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
                    raise ComfyError('Portable ComfyUI references must be existing project images.')
                name = 'orchestra-' + ref['id'] + path.suffix
                files[name] = path
                names[ref['slot']] = name
                ref_manifest.append({'slot': ref['slot'], 'role': ref.get('binding_role'), 'file': 'references/' + name, 'comfy_input_name': name})
            workflow = build_workflow(config, {**prepared, 'kind': kind, 'references': refs}, names)
            name = 'workflows/' + shot['id'] + '.json'
            workflows[name] = workflow
            manifest['shots'].append({'shot_id': shot['id'], 'workflow': name, 'references': ref_manifest, 'prompt': prepared, 'output_node': config['output_node']})
    except ComfyError as exc:
        raise StudioError('invalid_comfy_handoff', str(exc)) from exc
    folder = studio.media_root / project_id / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + '.zip'
    path = folder / filename
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        archive.writestr('README.txt', 'ComfyUI API workflows, not canvas JSON. Upload references/ files into ComfyUI input using the exact comfy_input_name values before queueing. Inspect your installed nodes/models and unmapped sampling settings. Read current Orchestra next_action and claim the permitted generation before executing. This revision snapshot grants no generation approval. Return the actual selected output through the current job ID; MP4 is required for video. Direct execution in Orchestra uploads references and returns validated media automatically. Imported custom workflows may contain private literals: review before sharing.\n')
        for name, workflow in workflows.items(): archive.writestr(name, json.dumps(workflow, indent=2, ensure_ascii=False))
        for name, file in files.items(): archive.write(file, 'references/' + name)
    return {'path': str(path), 'source_revision': project['revision'], 'download_url': f'/api/studio/export/{project_id}/{filename}'}
