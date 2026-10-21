import json
import uuid
import zipfile
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
