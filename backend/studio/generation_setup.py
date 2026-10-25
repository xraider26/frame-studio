"""Creator generator selections, separate from observed execution capabilities."""
import copy
import hashlib
import json

from .store import StudioError
from .generators import IMAGE_PROFILES, VIDEO_PROFILES

CONFIRMED_SOURCES = {'creator_statement', 'creator_delegation'}
SOURCES = CONFIRMED_SOURCES | {'legacy_unconfirmed', 'template_unconfirmed'}
FIELDS = {'executor', 'tool_name', 'profile', 'model', 'model_version_status', 'connection_id', 'selection_source', 'source_text'}


def validate_generation_setup(setup: dict, output_type: str) -> dict:
    if output_type not in {'image', 'video'} or not isinstance(setup, dict) or type(setup.get('version')) is not int or setup['version'] != 1 or set(setup) - {'version', 'image', 'video'}:
        raise StudioError('invalid_generation_setup', 'Provide version 1 with image/video selections; null explicitly defers a selection.')
    result = {'version': 1}
    for kind in ('image', 'video'):
        if kind not in setup:
            continue
        item = setup[kind]
        if item is None:
            result[kind] = None
            continue
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise StudioError('invalid_generation_setup', 'Each selection requires executor, tool_name, profile, model, model_version_status, connection_id, selection_source and source_text.')
        if any(not isinstance(item[key], str) for key in ('executor', 'profile', 'model_version_status', 'selection_source')):
            raise StudioError('invalid_generation_setup', 'Selection enum fields must be strings.')
        if item['executor'] not in {'agent_builtin', 'external_handoff', 'api', 'comfyui'} or item['model_version_status'] not in {'specified', 'managed', 'unknown'} or item['selection_source'] not in SOURCES:
            raise StudioError('invalid_generation_setup', 'Choose a supported executor, version status and selection source.')
        profiles = IMAGE_PROFILES if kind == 'image' else VIDEO_PROFILES
        if item['profile'] not in {p['id'] for p in profiles}:
            raise StudioError('invalid_generation_setup', 'Choose a supported prompt profile.')
        for key in ('tool_name', 'source_text'):
            if not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 8000:
                raise StudioError('invalid_generation_setup', 'Tool name and selection source text must be nonempty text of at most 8000 characters.')
        for key in ('model', 'connection_id'):
            if item[key] is not None and (not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 1000):
                raise StudioError('invalid_generation_setup', 'Model and connection ID must be null or nonempty text.')
        if item['model_version_status'] == 'specified' and not item['model']:
            raise StudioError('invalid_generation_setup', 'A specified model needs its supplied model name; use managed or unknown for opaque versions.')
        result[kind] = copy.deepcopy(item)
    return result


def selection_fingerprint(setup):
    return hashlib.sha256(json.dumps({key: setup.get(key) for key in ('version', 'image', 'video')}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def selection_ready(selection):
    return bool(selection and selection.get('selection_source') in CONFIRMED_SOURCES)


def generation_setup_state(project: dict | None, output_type: str | None = None) -> dict:
    output = output_type or (project or {}).get('output_type')
    if output is not None and output not in {'image', 'video'}:
        raise StudioError('invalid_output_type', 'Choose image or video output.')
    setup = copy.deepcopy((project or {}).get('generation_setup') or {'version': 1})
    kinds = ['image', 'video'] if output == 'video' else ['image']
    missing = [kind for kind in kinds if not selection_ready(setup.get(kind))]
    if output is None:
        questions = [{'id': 'output_type', 'prompt': 'Will this project need images, video, or both?', 'media_kinds': []}]
    elif missing:
        media = 'images and videos' if len(missing) == 2 else ('images' if missing == ['image'] else 'videos')
        questions = [{'id': 'generation_setup', 'prompt': f"Which generators will you use for {media}? You can use this AI's built-in image tool, another app, or a connected service.", 'media_kinds': missing}]
    else:
        questions = []
    return {'status': 'needs_input' if questions else 'ready', 'questions': questions,
            'required_selection_fields': sorted(FIELDS),
            'selections': setup, 'missing_media_kinds': missing,
            'output_type': output, 'adopted': bool((project or {}).get('generation_setup')),
            'instructions': 'Ask once per project, then only for changed or missing choices. Save choices already supplied by the creator instead of asking again. A saved destination is not a verified connection. Model versions may be managed or unknown.'}


def setup_from_explicit_settings(settings):
    """Compatibility for request-supplied choices only; never read merged template defaults."""
    setup = {'version': 1}
    for kind in ('image', 'video'):
        model = (settings or {}).get(kind + '_model')
        if isinstance(model, str) and model.strip():
            setup[kind] = {'executor': 'external_handoff', 'tool_name': model,
                'profile': (settings or {}).get(kind + '_generator', 'general_image' if kind == 'image' else 'flow_veo'),
                'model': model, 'model_version_status': 'specified', 'connection_id': None,
                'selection_source': 'creator_statement', 'source_text': 'Request supplied ' + kind + '_model: ' + model}
    return setup
