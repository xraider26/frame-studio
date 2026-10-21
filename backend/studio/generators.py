"""Prompt/export profiles, separate from execution credentials and API adapters."""
from string import Formatter

from .store import StudioError

VIDEO_PROFILES = [
    {'id': 'flow_veo', 'name': 'Google Flow / Veo', 'hint': 'Scene, action, camera and audio direction. Hand over to your Flow agent; no automatic account access.', 'source': 'https://deepmind.google/models/veo/prompt-guide/'},
    {'id': 'runway_i2v', 'name': 'Runway · image to video', 'hint': 'Uses the keyframe for appearance; keeps the prompt focused on visible motion. Sound notes stay separate.', 'source': 'https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide'},
    {'id': 'runway_t2v', 'name': 'Runway · text to video', 'hint': 'Describes both scene appearance and motion using positive phrasing.', 'source': 'https://help.runwayml.com/hc/en-us/articles/42460036199443-Text-to-Video-Prompting-Guide'},
    {'id': 'custom', 'name': 'Custom generator', 'hint': 'Use a prompt template for any other generator. Check its model capabilities before generating.'},
]
IMAGE_PROFILES = [
    {'id': 'general_image', 'name': 'General image generator', 'hint': 'Subject, composition, lens, light, palette and continuity.'},
    {'id': 'runway_image', 'name': 'Runway · image', 'hint': 'Visual descriptions and positive phrasing; exclusions remain separate notes.', 'source': 'https://help.runwayml.com/hc/en-us/articles/35694045317139-Gen-4-Image-Prompting-Guide'},
    {'id': 'custom', 'name': 'Custom image generator', 'hint': 'Set a reusable image prompt template.'},
]
FIELDS = {'subject', 'motion', 'camera', 'lighting', 'style', 'palette', 'framing', 'lens', 'continuity', 'narration', 'sound', 'aspect_ratio', 'duration'}


def validate_template(template):
    try:
        for _, key, spec, conversion in Formatter().parse(template):
            if key is not None and (key not in FIELDS or spec or conversion):
                raise ValueError()
    except ValueError as exc:
        raise StudioError('invalid_template', 'Use only simple supported placeholders: ' + ', '.join(sorted(FIELDS))) from exc


def prompt_for(project, shot, kind):
    settings = project['settings']
    values = {'subject': shot['image_prompt'], 'motion': shot['motion_prompt'], 'camera': settings['camera_move'],
              'lighting': settings['lighting'], 'style': settings['style'], 'palette': settings['palette'],
              'framing': settings['framing'], 'lens': settings['lens'], 'continuity': settings['continuity'],
              'narration': shot['narration'], 'sound': settings['sound'], 'aspect_ratio': settings['aspect_ratio'], 'duration': shot['duration_seconds']}
    profile = settings.get('image_generator', 'general_image') if kind == 'image' else settings.get('video_generator', 'flow_veo')
    visual = '{subject}. {framing}, {lens} lens. {lighting}. {style}, {palette}. {continuity}'
    if profile == 'custom':
        template = settings.get('custom_image_template' if kind == 'image' else 'custom_video_template') or (visual if kind == 'image' else '{subject}. {motion}. Camera: {camera}. {continuity}')
        validate_template(template)
    elif kind == 'image':
        template = visual
    elif profile == 'runway_i2v':
        template = '{motion}. Camera movement: {camera}. {continuity}'
    elif profile == 'runway_t2v':
        template = visual + '. {motion}. Camera movement: {camera}'
    else:
        template = visual + '. Action: {motion}. Camera: {camera}. Sound: {sound}. Dialogue/narration: {narration}'
    return {'generator_profile': profile, 'prompt': template.format_map(values).strip(),
            'negative_prompt': settings.get('negative_prompt', '') if profile not in ['runway_i2v', 'runway_t2v', 'runway_image'] else '',
            'separate_notes': {'sound': settings['sound'], 'narration': shot['narration'], 'avoid': settings.get('negative_prompt', '')},
            'duration_seconds': shot['duration_seconds'], 'aspect_ratio': settings['aspect_ratio']}
