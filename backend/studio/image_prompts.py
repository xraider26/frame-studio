"""Render still requirements without inventing creative or sampler decisions."""
import json


def render_image(prompt, project, shot, direction, profile):
    from .preflight import references_for
    req = direction['image']
    refs = references_for(project, shot, 'image')
    warnings = []
    negative = project['settings'].get('negative_prompt', '')
    # Preserve authored punctuation; only the compiler's empty scaffolding is cleaned.
    parts = [prompt]
    if req['mode'] == 'edit':
        # Recipe camera/light/style defaults are not requested edits to a supplied image.
        parts = ['Edit the supplied source image']
        if not refs or not any(r['role'] in ['character','location','prop','style','start_frame'] for r in direction['references']):
            warnings.append('Image editing needs an explicitly bound source image reference before execution.')
        if not req['instructions']:
            warnings.append('Describe the requested image edit explicitly.')
        if req['instructions']:
            parts.append('Requested changes: ' + req['instructions'])
        if shot['image_prompt'].strip():
            parts.append('Subject: ' + shot['image_prompt'].strip())
    elif req['instructions']:
        parts.append(req['instructions'])
    for label, value in [('Preserve', req['preserve']), ('Layout', req['layout']), ('Background', req['background'])]:
        if value:
            parts.append(label + ': ' + value)
    if req['exact_text']:
        parts.append('Render this exact visible text, preserving spelling and punctuation: ' + json.dumps(req['exact_text'], ensure_ascii=False))
        if negative == 'No text, logos or visual distortions':
            negative = 'visual distortions'
            warnings.append('Omitted the default text/logo exclusion because exact visible text was requested.')
        elif any(word in negative.casefold() for word in ['no text', 'text', 'letters', 'typography']):
            warnings.append('The custom exclusion may conflict with the requested visible text; review it before generation.')
    # These labels correspond to the ordered reference manifest, not invented native tokens.
    for index, ref in enumerate(refs, 1):
        binding = next((b for b in direction['references'] if b['slot'] == ref['slot']), {})
        role = ref.get('binding_role') or 'reference (role unspecified)'
        parts.append(f'Reference {index}, slot {ref["slot"]}: {role}' + ('. ' + binding['notes'] if binding.get('notes') else ''))
    if profile == 'custom':
        # Custom syntax is user-owned. Requirements remain available as structured notes.
        rendered = prompt
        if any(req[k] for k in ['instructions', 'preserve', 'exact_text', 'layout', 'background']):
            warnings.append('Custom prompt text is preserved. Incorporate the structured image requirements into your custom template or workflow.')
    else:
        rendered = '. '.join(p for p in parts if p)
    if profile == 'midjourney_image':
        rendered = rendered.rstrip(' .') + ' --ar ' + project['settings']['aspect_ratio']
    avoidance_notes = negative
    if profile in ['runway_image', 'flux_image', 'midjourney_image']:
        negative = ''
    if profile == 'qwen_image' and req['background']:
        warnings.append('Transparency requires an RGBA-capable workflow/output; background wording alone does not enable alpha.')
    return rendered, negative, warnings, avoidance_notes
