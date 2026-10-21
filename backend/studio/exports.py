import json
import uuid
import zipfile
import csv
import io
from pathlib import Path

from .generators import prompt_for
from .preflight import preflight
from .knowledge import knowledge_catalog


def export_project(studio, project):
    p = project
    included = {}
    for asset in p['assets']:
        if asset.get('role') == 'reference' or any(s.get('image_asset') == asset['id'] for s in p['shots']):
            file = Path(asset['path']).resolve()
            if file.is_relative_to(studio.media_root) and file.is_file():
                included[asset['id']] = (file, 'references/' + file.name)
    active = studio._next(p)
    manifest = {'schema_version': 2, 'package_type': 'studio_generation_handoff', 'project_id': p['id'], 'project_name': p['name'],
                'source_revision': p['revision'], 'execution_mode': 'external_agent',
                'video_generator': p['settings']['video_generator'], 'image_generator': p['settings']['image_generator'],
                'creative_settings': p['settings'], 'documents': p['documents'], 'approval_policy': p['approval_policy'],
                'production': p['production'], 'preflight': preflight(p), 'source_coverage': knowledge_catalog()['coverage'],
                'step_status': p['steps'], 'next_action_at_export': active,
                'references': [{'asset_id': key, 'file': rel} for key, (_, rel) in included.items()],
                'shots': [{'shot_id': s['id'], 'order': i, 'title': s['title'],
                           'direction': s['direction'], 'retained_edit_duration_seconds': s.get('edit_duration_seconds', s['duration_seconds']),
                           'image': prompt_for(p, s, 'image'), 'video': prompt_for(p, s, 'video'),
                           'start_frame': included.get(s['image_asset'], (None, None))[1],
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
                     d['sound']['ambience'], d['sound']['foley'], d['sound']['music'], d['action']['transition']])
    manifest['warnings'] = warnings
    manifest['ready'] = manifest['ready'] and not warnings and not manifest['preflight']['errors']
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['order', 'shot_id', 'scene_id', 'title', 'file', 'timeline_in', 'timeline_out', 'source_in', 'source_out', 'narration', 'dialogue', 'speaker', 'captions', 'ambience', 'foley', 'music', 'transition'])
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
