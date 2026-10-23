"""Paraphrased review of a creator-supplied guide, with editable studio-authored setups."""
import copy

GUIDE = {
    'id': 'shared-prompt-architecture-2026-10-23', 'version': 1,
    'title': 'Prompt architecture: reviewed practical guidance',
    'source_url': 'https://share.gemini.google/hK8ldZB3TdxP',
    'reviewed_at': '2026-10-23', 'provenance': 'user_supplied_ai_report_reviewed',
    'guarantees_output': False,
    'principles': [
        'Lead still-image descriptions with a concrete subject and meaningful pose.',
        'Separate camera motion from subject action in video instructions.',
        'Prefer one readable action and one intentional camera move per short shot.',
        'For image-to-video, use the image for appearance and describe the changes.',
        'Specify motivated light, material response, contact and relevant surface detail.',
        'Match linework, texture, shading and palette to the chosen art style.',
        'Use model-specific syntax; preserve unsupported requirements as separate notes.',
        'Inspect results and revise a named defect rather than adding quality slogans.',
    ],
    'corrections': [
        'Generation remains probabilistic; structural prompts do not ensure repeatability.',
        'A universal first-15-token rule and exact colour reproduction are not established.',
        'Negative conditioning varies by model and interface; do not remove it globally.',
        'Perspective depends on viewpoint; focal length alone does not change perspective.',
        'Depth of field depends on several factors; wide lenses and close focus can coexist.',
        'Numeric generation settings and historical film claims require independent verification.',
    ],
    'scope': 'Practical heuristics and studio-authored examples; not an authoritative architecture specification or verified provider capability catalogue.',
}

SETUPS = [
    {'id': 'editorial-study', 'name': 'Controlled editorial', 'intent': 'Readable subjects and faithful material detail.',
     'apply': {'camera': {'framing': 'Medium close composition', 'lens': '85mm portrait appearance cue', 'aperture': 'Subject detail readable; gently separated background'}, 'lighting': {'technique': 'Large soft key with restrained fill', 'world_source': 'Soft source to one side, fill opposite', 'material_response': 'Preserve surface texture and highlight detail'}, 'art': {'style': 'Editorial photography', 'texture': 'Natural skin and material detail', 'palette': 'Restrained warm neutrals'}}},
    {'id': 'narrative-study', 'name': 'Atmospheric narrative', 'intent': 'Use light and depth to support a dramatic moment.',
     'apply': {'camera': {'lens': '35mm environmental appearance cue', 'body_look': 'Restrained anamorphic-inspired highlights', 'framing': 'Environmental medium shot'}, 'lighting': {'technique': 'Motivated practical sources', 'contrast': 'Readable subject within shaped shadows'}, 'art': {'style': 'Atmospheric narrative cinema', 'palette': 'Cool ambient light with warm motivated accents'}}},
    {'id': 'drawn-study', 'name': 'Drawn graphic world', 'intent': 'Maintain a coherent illustrated treatment.',
     'apply': {'camera': {'framing': 'Clear silhouette with layered drawn depth', 'lens': 'Drawn perspective; no physical camera required'}, 'lighting': {'technique': 'Designed cel-shaded light shapes'}, 'art': {'style': 'Hand-drawn 2D illustration', 'materials': 'Consistent ink contours and painted backgrounds', 'texture': 'Controlled line weight and paper texture', 'palette': 'Limited complementary colours'}}},
    {'id': 'isometric-study', 'name': 'Isometric miniature', 'intent': 'Explain a spatial idea with clear geometry.',
     'apply': {'camera': {'framing': 'Isometric miniature composition', 'lens': 'Orthographic projection cue'}, 'lighting': {'technique': 'Soft studio dome and a directional key', 'material_response': 'Ground objects with contact shadows'}, 'art': {'style': 'Stylised miniature 3D render', 'materials': 'Matte plastic, frosted glass and restrained metal', 'palette': 'Coherent muted pastel palette'}}},
    {'id': 'analog-study', 'name': 'Tactile analog mood', 'intent': 'Suggest a nostalgic captured moment.',
     'apply': {'camera': {'body_look': 'Restrained film-inspired grain and highlight bloom', 'lens': 'Vintage lens appearance with gentle edge falloff'}, 'lighting': {'technique': 'Motivated low warm light'}, 'art': {'style': 'Analog-inspired observational image', 'texture': 'Subtle grain without obscuring the subject', 'palette': 'Warm earthy tones and soft paper whites'}}},
]


def prompting_guide():
    return copy.deepcopy(GUIDE)


def style_setups():
    return copy.deepcopy(SETUPS)
