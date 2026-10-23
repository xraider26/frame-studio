import json
import uuid
import zipfile
import csv
import io
from pathlib import Path

from .generators import prompt_for
from .preflight import preflight, references_for
from .knowledge import knowledge_catalog
from .recipes import recipe_context
from .sequences import sequence_context


def export_project(studio, project):
    p = project
    if p.get('output_type') == 'image':
        return export_images(studio, p)
    included = {}
    used = {a['id'] for shot in p['shots'] for kind in ['image', 'video'] for a in references_for(p, shot, kind)}
    for asset in p['assets']:
        if asset['id'] in used:
            file = Path(asset['path']).resolve()
            if file.is_relative_to(studio.media_root) and file.is_file():
                included[asset['id']] = (file, 'references/' + asset['id'] + file.suffix)
    active = studio._next(p)
    manifest = {'schema_version': 2, 'package_type': 'studio_generation_handoff', 'project_id': p['id'], 'project_name': p['name'],
                'source_revision': p['revision'], 'execution_mode': 'external_agent', 'recipe_contract': recipe_context(p), 'sequence_context': sequence_context(p),
                'video_generator': p['settings']['video_generator'], 'image_generator': p['settings']['image_generator'],
                'creative_settings': p['settings'], 'documents': p['documents'], 'approval_policy': p['approval_policy'],
                'production': p['production'], 'preflight': preflight(p), 'source_coverage': knowledge_catalog()['coverage'],
                'step_status': p['steps'], 'next_action_at_export': active,
                'references': [{'asset_id': key, 'file': rel} for key, (_, rel) in included.items()],
                'shots': [{'shot_id': s['id'], 'order': i, 'title': s['title'],
                           'direction': s['direction'], 'retained_edit_duration_seconds': s.get('edit_duration_seconds', s['duration_seconds']),
                           'image': prompt_for(p, s, 'image'), 'video': prompt_for(p, s, 'video'),
                           'start_frame': included.get(s['image_asset'], (None, None))[1],
                           'reference_files': {kind: [{'asset_id': a['id'], 'slot': a['slot'], 'role': a.get('binding_role'), 'file': included.get(a['id'], (None, None))[1]} for a in references_for(p, s, kind)] for kind in ['image', 'video']},
                           'expected_outputs': {'image': f'shot_{i:02d}_image.png', 'video': f'shot_{i:02d}_video.mp4'}} for i, s in enumerate(p['shots'], 1)],
                'return_contract': {'method': 'MCP claim_generation -> return_generation',
                                    'instructions': 'Connect to this studio and read its current next_action. Claim each permitted generation with its exact job_id. Save real outputs in the returned inbox, then return_generation. Do not bypass required reviews. Offline outputs can be imported later using the same shot IDs after claiming their current task.'}}
    lines = [f'# {p["name"]}', '', f'Generator handoff · revision {p["revision"]}', '',
             f'Video profile: {manifest["video_generator"]}', f'Image profile: {manifest["image_generator"]}', '',
             'This package contains prompts and available references. It is not a generated video or an automatic Flow import.', '',
             'Check the current studio review status before starting generation. This exported file is a snapshot; it cannot grant approval or override later changes.', '']
    for s in manifest['shots']:
        lines += [f'## {s["order"]:02d} / {s["title"]}', '', '### Image', s['image']['prompt'], '', '### Video', s['video']['prompt'], '',
                  f'Target duration: {s["video"]["duration_seconds"]}s; aspect: {s["video"]["aspect_ratio"]}. Confirm support in your selected model.',
                  f'Start frame: {s["start_frame"] or "Generate/return the keyframe first"}',
                  'Separate audio / avoidance notes: ' + json.dumps(s['video']['separate_notes'], ensure_ascii=False), '']
    text = '\n'.join(lines)
    folder = studio.media_root / p['id'] / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + '.zip'
    path = folder / name
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        archive.writestr('prompts.md', text)
        archive.writestr('techniques.json', json.dumps(knowledge_catalog(), indent=2, ensure_ascii=False))
        contract = manifest['recipe_contract']
        archive.writestr('production-recipe.json', json.dumps(contract, indent=2, ensure_ascii=False))
        if contract['active']:
            recipe_text = [f'# {contract["name"]} · recipe v{contract["version"]}', '', contract['intent'], '', '## Creative decisions', *contract['decision_requirements']]
            for stage, instructions in contract['stage_instructions'].items():
                recipe_text += ['', '## ' + stage.replace('_', ' '), *['- ' + v for v in instructions]]
            recipe_text += ['', '## Source rules', *[f'- {v["section"]}: {v["teaching"]} Correction: {v["correction"]}' for v in contract['source_rules']]]
            archive.writestr('production-recipe.md', '\n'.join(recipe_text))
        archive.writestr('README.txt', 'Give manifest.json and prompts.md to your generator agent, plus the references folder.\nThis is a portable planning package, not native Flow/Runway project format.\nUse the selected generator profile and check its actual model/settings.\nFollow the current approval policy in the studio before generating.\nReturn outputs through MCP with the current job ID; do not claim completion without real files.\n')
        for file, rel in included.values():
            archive.write(file, rel)
    return {'manifest': manifest, 'markdown': text, 'path': str(path), 'download_url': f'/api/studio/export/{p["id"]}/{name}'}


def export_editor(studio, project_id):
    manifest = studio.editor_handoff(project_id)
    warnings = []
    included = []
    rows = []
    for index, shot in enumerate(manifest['shots'], 1):
        asset = shot['video']
        relative = ''
        if asset:
            file = Path(asset['path']).resolve()
            if file.is_relative_to(studio.media_root) and file.is_file():
                relative = f'media/{index:03d}_{asset["id"]}.mp4'
                included.append((file, relative))
                if asset.get('duration', 0) + .1 < shot['source_out']:
                    warnings.append(f'{shot["title"]}: chosen source range exceeds actual returned clip duration.')
            else:
                warnings.append(f'{shot["title"]}: selected video file is missing.')
        else:
            warnings.append(f'{shot["title"]}: no video take selected.')
        shot['portable_video'] = relative or None
        d = shot['effective_direction']
        rows.append([index, shot['id'], shot['direction']['scene_id'], shot['title'], relative,
                     shot['timeline_in'], shot['timeline_out'], shot['source_in'], shot['source_out'],
                     shot['narration'], d['sound']['dialogue'], d['sound']['speaker_id'], d['sound']['captions'],
                     d['sound']['ambience'], d['sound']['foley'], d['sound']['music'], d['action']['transition'],
                     d['editorial']['coverage_role'], d['editorial']['purpose'], d['editorial']['transition_in'], d['editorial']['audio_source_shot_id'], d['editorial']['audio_continuity']])
    manifest['warnings'] = warnings
    manifest['ready'] = manifest['ready'] and not warnings and not manifest['preflight']['errors']
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['order', 'shot_id', 'scene_id', 'title', 'file', 'timeline_in', 'timeline_out', 'source_in', 'source_out', 'narration', 'dialogue', 'speaker', 'captions', 'ambience', 'foley', 'music', 'transition', 'coverage_role', 'coverage_purpose', 'transition_in', 'audio_source_shot_id', 'audio_continuity'])
    writer.writerows(rows)
    name = uuid.uuid4().hex + '.zip'
    folder = studio.media_root / project_id / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('editor-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr('edit-decision.csv', stream.getvalue().encode('utf-8-sig'))
        archive.writestr('README.txt', 'External editing package. Assemble the selected takes using source and timeline ranges in edit-decision.csv.\nThis is not a native Resolve/Premiere/CapCut project. Captions/audio/colour are directions for your editor.\nInspect warnings and actual duration. Review the final export before returning it to the studio.\n')
        for file, relative in included:
            archive.write(file, relative)
    return {'manifest': manifest, 'path': str(path), 'download_url': f'/api/studio/export/{project_id}/{name}'}


def export_images(studio, p):
    """Portable still-image delivery with actual selected files and image prompts."""
    included = []
    references = {}
    for shot in p['shots']:
        for asset in references_for(p, shot, 'image'):
            file = Path(asset['path']).resolve()
            if file.is_relative_to(studio.media_root) and file.is_file():
                references[asset['id']] = 'references/' + asset['id'] + file.suffix
                if not any(relative == references[asset['id']] for _, relative in included):
                    included.append((file, references[asset['id']]))
    shots = []
    for index, shot in enumerate(p['shots'], 1):
        asset = next((a for a in p['assets'] if a['id'] == shot.get('image_asset') and a['kind'] == 'image' and not a.get('stale')), None)
        relative = None
        if asset:
            file = Path(asset['path']).resolve()
            if file.is_relative_to(studio.media_root) and file.is_file():
                relative = f'images/{index:03d}_{asset["id"]}{file.suffix}'
                included.append((file, relative))
        shots.append({'shot_id': shot['id'], 'order': index, 'title': shot['title'], 'image': prompt_for(p, shot, 'image'),
                      'selected_asset_id': asset['id'] if relative else None, 'selected_image': relative,
                      'reference_files': [{'asset_id': a['id'], 'slot': a['slot'], 'file': references.get(a['id'])} for a in references_for(p, shot, 'image')],
                      'expected_outputs': {'image': f'shot_{index:02d}_image.png'}})
    from .intake import creative_intake
    manifest = {'schema_version': 2, 'package_type': 'studio_image_delivery', 'output_type': 'image',
                'project_id': p['id'], 'project_name': p['name'], 'source_revision': p['revision'],
                'creative_settings': p['settings'], 'creative_intake': creative_intake(p), 'documents': p['documents'],
                'approval_policy': p['approval_policy'], 'production': p['production'], 'shots': shots, 'references': [{'asset_id': key, 'file': value} for key, value in references.items()],
                'image_generator': p['settings']['image_generator'],
                'next_action_at_export': studio._next(p), 'preflight': preflight(p)}
    text = '\n'.join([f'# {p["name"]}', '', *[f'{s["order"]}. {s["title"]}\n{s["image"]["prompt"]}\nSelected image: {s["selected_image"] or "None"}' for s in shots]])
    folder = studio.media_root / p['id'] / 'exports'
    folder.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + '.zip'
    path = folder / name
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        archive.writestr('prompts.md', text)
        archive.writestr('README.txt', 'Portable image planning and delivery package. Read manifest.json and prompts.md; references/ contains actual available reference images and images/ contains actual selected outputs when present.\nBefore generation, connect to the studio and follow current next_action, approvals, quality requirements and budget policy. This package is a revision snapshot, not permission to bypass current gates.\nUse image_generator and the exact image model in creative_settings; verify the model capabilities. Return actual outputs through the current MCP job or import_external_take, then inspect and explicitly select imported takes.\n')
        for file, relative in included:
            archive.write(file, relative)
    return {'manifest': manifest, 'markdown': text, 'path': str(path), 'download_url': f'/api/studio/export/{p["id"]}/{name}'}
