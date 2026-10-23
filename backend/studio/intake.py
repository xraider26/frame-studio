"""Creator answers and documented prompt-family guidance; never an automatic creative judge."""
from .store import StudioError

ANSWER_FIELDS = ('vision', 'art_style', 'purpose', 'audience', 'constraints')
QUESTIONS = {
    'vision': 'What should we see, and what feeling or message should the finished work convey?',
    'art_style': 'What art style or visual treatment do you want? Share a reference, describe it, or ask me to propose options.',
    'purpose': 'Where will this be used, and what should it achieve?',
    'image_model': 'Which image generator and exact model/version will you use?',
    'video_model': 'Which video generator and exact model/version will you use?',
}


def validate_intake(value):
    if not isinstance(value, dict) or any(key not in ANSWER_FIELDS for key in value):
        raise StudioError('invalid_intake', 'Creative intake must contain vision, art_style, purpose, audience or constraints.')
    if any(not isinstance(text, str) or len(text) > 8000 for text in value.values()):
        raise StudioError('invalid_intake', 'Each creative answer must be text of at most 8000 characters.')
    return {key: text.strip() for key, text in value.items()}


def creative_intake(project):
    settings = project.get('settings', {})
    answers = dict(settings.get('creative_intake') or {})
    required = bool(project.get('creative_intake_required'))
    missing = [key for key in ('vision', 'art_style', 'purpose') if not answers.get(key, '').strip()]
    if not settings.get('image_model', '').strip():
        missing.append('image_model')
    if project.get('output_type', 'video') == 'video' and not settings.get('video_model', '').strip():
        missing.append('video_model')
    instructions = (
        'Ask the creator the missing important questions before choosing a technical setup or preparing generation prompts. '
        'Group the questions into one concise message; do not ask again for saved answers. '
        'Never treat a recipe default as the creator\'s chosen vision or art style. '
        'If they ask you to recommend a style, propose a small set of relevant options and save their choice; '
        'if they explicitly delegate the choice, record that delegation and the selected recommendation in the answer. '
        'Use the saved vision, purpose, style and references to explain and select camera, framing, lens, lighting and palette. '
        'Keep these choices editable. Approval switches govern reviews, not whether missing creative intent can be invented. '
        'Save answers using update_settings with creative_intake; save exact model names using image_model/video_model. '
        'Check the actual connected model capabilities before generation. A prompt profile does not connect an account.'
    )
    style = answers.get('art_style', '').lower()
    suggested = {}
    if not missing:
        suggested = {
            'art_style': answers['art_style'],
            'decision_basis': answers['vision'] + ' / ' + answers['purpose'],
            'guidance': 'Choose composition and physical light sources to serve this brief, retain explicit creator overrides, and inspect a representative result.',
        }
        if any(word in style for word in ['watercol', 'illustrat', 'anime', '2d', 'painting']):
            suggested['camera_and_light'] = 'Describe drawn perspective, depth layers, value grouping and painted light; photographic camera brands are optional appearance cues.'
        elif any(word in style for word in ['product', 'studio', 'advert']):
            suggested['camera_and_light'] = 'Consider controlled product framing, readable silhouette, motivated key/fill and material highlights; verify brand details against references.'
        else:
            suggested['camera_and_light'] = 'Choose shot size, viewpoint, depth and motivated lighting for the intended emotion; avoid adding movement without a story purpose.'
    return {
        'status': ('needs_input' if missing else 'ready') if required else 'legacy',
        'questions': [{'id': key, 'prompt': QUESTIONS[key]} for key in missing],
        'answers': answers, 'instructions': instructions, 'suggested_setup': suggested,
    }


def model_guidance(profile, model, kind):
    """Known families are guidance, not live capability or account verification."""
    normalized = model.casefold().replace('_', '-').strip()
    source = None
    documented = False
    if kind == 'video' and profile == 'flow_veo' and normalized in {'veo 3', 'veo 3.1', 'veo-3', 'veo-3.1'}:
        documented = True
        source = 'https://deepmind.google/models/veo/prompt-guide/'
        instructions = 'Use a coherent scene with subject, setting, action, framing and camera movement. Describe motivated sound and dialogue separately within the scene. Verify actual duration, references and audio controls in the selected model.'
    elif kind == 'video' and ((profile == 'runway_i2v' and normalized in {'gen-4', 'gen-4 turbo', 'gen-4.5', 'gen4', 'gen4.5'}) or (profile == 'runway_t2v' and normalized in {'gen-4.5', 'gen4.5'})):
        documented = True
        source = 'https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide' if profile == 'runway_i2v' else 'https://academy.runwayml.com/guides/prompting-guide'
        instructions = 'Use direct positive visual language for motion, camera work and temporal progression. For image-to-video, let the reference establish appearance and focus the text on motion. Keep sound and avoidance requirements in separate notes; verify model capabilities.'
    elif kind == 'image' and profile == 'runway_image' and normalized in {'gen-4', 'gen-4 image', 'gen4', 'gen4 image'}:
        documented = True
        source = 'https://help.runwayml.com/hc/en-us/articles/35694045317139-Gen-4-Image-Prompting-Guide'
        instructions = 'Describe the subject, scene, composition, light and aesthetic with positive visual language. Put avoidance requirements in separate notes. Bind actual image references explicitly and verify available controls.'
    else:
        instructions = 'Verify this exact model\'s current official prompting guide and capabilities before generation. Use the selected profile/custom template as a starting point; do not invent model-specific parameters or native syntax.'
    return {'model': model, 'profile': profile, 'status': 'documented' if documented else 'custom_unverified',
            'instructions': instructions, 'source': source, 'checked_at': '2026-10-23' if documented else None}
