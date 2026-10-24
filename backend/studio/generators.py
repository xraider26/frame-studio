"""Prompt/export profiles, separate from execution credentials and API adapters."""
from string import Formatter
import json

from .store import StudioError
from .creative import effective_direction
from .recipes import recipe_context, recipe_criteria
from .intake import model_guidance

VIDEO_PROFILES = [
    {'id': 'minimax_h3', 'name': 'MiniMax H3', 'hint': 'Scene followed by shots, motion and audio in one prompt. Bind references to the actual workflow inputs.', 'source': 'https://docs.comfy.org/tutorials/video/minimax/minimax-h3-native'},
    {'id': 'flow_veo', 'name': 'Google Flow / Veo', 'hint': 'Scene, action, camera and audio direction. Hand over to your Flow agent; no automatic account access.', 'source': 'https://deepmind.google/models/veo/prompt-guide/'},
    {'id': 'runway_i2v', 'name': 'Runway · image to video', 'hint': 'Uses the keyframe for appearance; keeps the prompt focused on visible motion. Sound notes stay separate.', 'source': 'https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide'},
    {'id': 'runway_t2v', 'name': 'Runway · text to video', 'hint': 'Describes both scene appearance and motion using positive phrasing.', 'source': 'https://help.runwayml.com/hc/en-us/articles/42460036199443-Text-to-Video-Prompting-Guide'},
    {'id': 'custom', 'name': 'Custom generator', 'hint': 'Use a prompt template for any other generator. Check its model capabilities before generating.'},
]
IMAGE_PROFILES = [
    {'id': 'qwen_image', 'name': 'Qwen · image generation / editing', 'hint': 'Detailed natural language, exact text and explicit edit/preserve instructions. Verify the installed workflow and model version.', 'source': 'https://github.com/QwenLM/Qwen-Image-2.1'},
    {'id': 'general_image', 'name': 'General image generator', 'hint': 'Subject, composition, lens, light, palette and continuity.'},
    {'id': 'runway_image', 'name': 'Runway · image', 'hint': 'Visual descriptions and positive phrasing; exclusions remain separate notes.', 'source': 'https://help.runwayml.com/hc/en-us/articles/35694045317139-Gen-4-Image-Prompting-Guide'},
    {'id': 'flux_image', 'name': 'FLUX · image', 'hint': 'Natural visual descriptions. Avoidance requirements stay in separate notes; no native negative field is emitted.', 'source': 'https://help.bfl.ai/articles/7734566352-does-flux-2-support-negative-prompting'},
    {'id': 'midjourney_image', 'name': 'Midjourney · image', 'hint': 'Visual description followed by the selected aspect-ratio parameter. Verify version-specific controls separately.', 'source': 'https://docs.midjourney.com/hc/en-us/articles/32859204029709-Parameter-List'},
    {'id': 'custom', 'name': 'Custom image generator', 'hint': 'Set a reusable image prompt template.'},
]
for _profile in VIDEO_PROFILES:
    _profile['suggested_models'] = {'flow_veo': ['Veo 3.1', 'Veo 3'], 'runway_i2v': ['Gen-4.5', 'Gen-4', 'Gen-4 Turbo'], 'runway_t2v': ['Gen-4.5']}.get(_profile['id'], [])
    if _profile['id'] == 'minimax_h3': _profile['suggested_models'] = ['MiniMax H3']
for _profile in IMAGE_PROFILES:
    _profile['suggested_models'] = {'runway_image': ['Gen-4 Image'], 'flux_image': ['FLUX.2', 'FLUX.1'], 'midjourney_image': ['V7', 'V6.1']}.get(_profile['id'], [])
    if _profile['id'] == 'qwen_image': _profile['suggested_models'] = ['Qwen-Image-2.1', 'Qwen-Image-2.1-Turbo']
FIELDS = {'subject', 'motion', 'camera', 'lighting', 'style', 'palette', 'framing', 'lens', 'continuity', 'narration', 'sound', 'aspect_ratio', 'duration', 'environment', 'mood', 'opening', 'ending', 'dialogue', 'composition', 'body_look', 'state_before', 'state_after', 'references'}


def validate_template(template):
    try:
        for _, key, spec, conversion in Formatter().parse(template):
            if key is not None and (key not in FIELDS or spec or conversion):
                raise ValueError()
    except ValueError as exc:
        raise StudioError('invalid_template', 'Use only simple supported placeholders: ' + ', '.join(sorted(FIELDS))) from exc


def prompt_for(project, shot, kind):
    settings = project['settings']
    d = effective_direction(project, shot)
    camera, light, art, action, sound = (d[k] for k in ['camera', 'lighting', 'art', 'action', 'sound'])
    def join(*values):
        return '; '.join(str(v).strip() for v in values if v not in ['', None, [], {}])
    def named(mapping):
        return join(*(f'{key.replace("_", " ")}: {value}' for key, value in mapping.items() if value not in ['', None, [], {}]))
    entities = set(action['visible_entities']) | {r['entity_id'] for r in d['references']}
    bible_fields = ['name', 'identity', 'wardrobe', 'layout', 'light_sources', 'materials'] + (['voice'] if kind == 'video' else [])
    bible = join(*(named({k: e[k] for k in bible_fields}) for e in project['production']['bible'] if e['id'] in entities))
    state_before = json.dumps(action['state_before'], ensure_ascii=False) if action['state_before'] else ''
    state_after = json.dumps(action['state_after'], ensure_ascii=False) if action['state_after'] else ''
    continuity = join(settings['continuity'], bible, f'State before: {state_before}' if state_before else '', f'State after: {state_after}' if state_after else '', action['transition'])
    if kind == 'image': continuity = join(settings['continuity'], bible)
    timed = join(*(f'{b["start"]:g}–{b["end"]:g}s: {b["description"]}' for b in action['beats']))
    values = {'subject': shot['image_prompt'], 'motion': join(action['primary_action'] or shot['motion_prompt'], f'Opening: {action["opening"]}' if action['opening'] else '', f'Ending: {action["ending"]}' if action['ending'] else '', timed),
              'camera': named({k: camera[k] for k in ['move', 'speed', 'start_framing', 'end_framing', 'move_timing']}),
              'lighting': named(light), 'style': join(art['style'], art['materials'], art['texture']), 'palette': art['palette'],
              'framing': join(camera['framing'], camera['angle'], camera['position']), 'lens': join(camera['lens'], camera['aperture']),
              'continuity': continuity, 'narration': shot['narration'], 'sound': named({k: sound[k] for k in ['ambience', 'foley', 'music', 'voice']}),
              'aspect_ratio': settings['aspect_ratio'], 'duration': shot['duration_seconds'], 'environment': d['environment'], 'mood': d['mood'],
              'opening': action['opening'], 'ending': action['ending'], 'dialogue': sound['dialogue'],
              'composition': named({k: camera[k] for k in ['foreground', 'midground', 'background', 'lead_room', 'screen_direction']}),
              'body_look': camera['body_look'], 'state_before': state_before, 'state_after': state_after,
              'references': named({r['slot']: f'{r["asset_id"]}@v{r["version"]} ({r["role"]})' for r in d['references']})}
    profile = settings.get('image_generator', 'general_image') if kind == 'image' else settings.get('video_generator', 'flow_veo')
    model = settings.get('image_model' if kind == 'image' else 'video_model', '')
    intake = settings.get('creative_intake') or {}
    guidance = model_guidance(profile, model, kind)
    visual = '{subject}. {environment}. {framing}; {lens}. {composition}. {body_look}. {lighting}. {style}; {palette}. {mood}. {continuity}'
    if profile == 'custom':
        template = settings.get('custom_image_template' if kind == 'image' else 'custom_video_template') or (visual if kind == 'image' else '{subject}. {motion}. Camera: {camera}. {continuity}')
        validate_template(template)
    elif kind == 'image':
        template = visual
    elif profile == 'runway_i2v':
        template = 'Camera movement: {camera}. {motion}. {continuity}'
    elif profile == 'runway_t2v':
        template = 'Camera movement: {camera}. ' + visual + '. {motion}'
    else:
        template = 'Camera movement: {camera}. ' + visual + '. Action: {motion}. Sound: {sound}. Dialogue: {dialogue}. Narration: {narration}'
    if kind == 'video' and profile == 'minimax_h3':
        template = visual + '. Shots and action: {motion}. Camera: {camera}. Dialogue: {dialogue}. Sound: {sound}. Narration: {narration}'
    # Empty optional fields should not leave unreadable punctuation-only sentences.
    rendered = '. '.join(part.strip(' ;') for part in template.format_map(values).split('. ') if part.strip(' ;.'))
    # Appearance comes from the reference in I2V; retain the full brief in metadata.
    # Intended use stays in separate notes so the visual subject leads the prompt.
    negative = settings.get('negative_prompt', '') if profile not in ['runway_i2v', 'runway_t2v', 'runway_image', 'flux_image', 'midjourney_image', 'minimax_h3'] else ''
    warnings = []
    avoidance_notes = settings.get('negative_prompt', '')
    if kind == 'image':
        from .image_prompts import render_image
        # Preserve exact custom-template punctuation, including decimals and native syntax.
        if profile == 'custom': rendered = template.format_map(values).strip()
        rendered, negative, warnings, avoidance_notes = render_image(rendered, project, shot, d, profile)
    return {'generator_profile': profile, 'model': model, 'model_guidance': guidance,
            'creative_intent': intake, 'prompt': rendered.strip(), 'effective_direction': d, 'recipe_contract': recipe_context(project, shot),
            'negative_prompt': negative, 'warnings': warnings, 'image_requirements': d['image'] if kind == 'image' else None,
            'separate_notes': {'purpose': intake.get('purpose', ''), 'sound': sound, 'narration': shot['narration'], 'avoid': avoidance_notes, 'reference_map': d['references'], 'acceptance_criteria': list(dict.fromkeys(recipe_criteria(project, shot, kind) + d['quality']['criteria'])), 'generation_mode': d['generation_mode']},
            'duration_seconds': shot['duration_seconds'], 'aspect_ratio': settings['aspect_ratio']}
