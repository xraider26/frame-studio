STEPS = ['brief', 'script', 'visual_direction', 'pilot', 'production', 'editor_handoff', 'final_review']
LABELS = ['Brief', 'Script', 'Visual direction', 'Pilot', 'Production', 'Editor handoff', 'Final review']
TEMPLATES = [
    {'id': 'ai-film', 'name': 'AI film', 'description': 'Cinematic scenes with a consistent world.', 'structure': ['Opening image', 'Discovery', 'Payoff'], 'aspect': '16:9'},
    {'id': 'ugc', 'name': 'UGC', 'description': 'A natural hook, demonstration and takeaway.', 'structure': ['Creator hook', 'Product demo', 'Takeaway'], 'aspect': '9:16'},
    {'id': 'short-drama', 'name': 'Short drama', 'description': 'Character, conflict and a compelling turn.', 'structure': ['Hook', 'Conflict', 'Reversal'], 'aspect': '9:16'},
    {'id': 'advertisement', 'name': 'Advertisement', 'description': 'A clear product story with a strong finish.', 'structure': ['Problem', 'Product benefit', 'Call to action'], 'aspect': '9:16'},
    {'id': 'explainer', 'name': 'Explainer', 'description': 'Make one useful idea easy to understand.', 'structure': ['Question', 'Explanation', 'Example'], 'aspect': '16:9'},
    {'id': 'podcast', 'name': 'Podcast', 'description': 'An opening thought, conversation and conclusion.', 'structure': ['Opening thought', 'Discussion', 'Closing point'], 'aspect': '16:9'},
    {'id': '2d-animation', 'name': '2D animation', 'description': 'Illustrated scenes with a locked visual style.', 'structure': ['Establish', 'Animate', 'Resolve'], 'aspect': '16:9'},
    {'id': 'claymation', 'name': 'Claymation', 'description': 'Tactile characters and deliberate motion.', 'structure': ['Introduce', 'Action', 'Reaction'], 'aspect': '16:9'},
    {'id': 'custom', 'name': 'Custom', 'description': 'Build your own format and shot structure.', 'structure': ['Opening', 'Development', 'Closing'], 'aspect': '16:9'},
]
DEFAULT_SETTINGS = {'image_model': '', 'video_model': '', 'creative_intake': {}, 'aspect_ratio': '16:9', 'platform': 'YouTube', 'duration_seconds': 30,
                    'audience': '', 'lens': '35mm', 'framing': 'Medium shot',
                    'camera_move': 'Slow dolly in', 'lighting': 'Soft directional light',
                    'palette': 'Warm amber', 'style': 'Cinematic realism', 'continuity': '',
                    'sound': 'Scene-motivated ambience', 'negative_prompt': 'No text, logos or visual distortions',
                    'generation_mode': 'external_agent', 'video_generator': 'flow_veo', 'image_generator': 'general_image',
                    'custom_video_template': '{subject}. {motion}. Camera: {camera}. {continuity}',
                    'custom_image_template': '{subject}. {framing}, {lens}. {lighting}. {style}. {continuity}'}


IMAGE_STEPS = ['brief', 'script', 'visual_direction', 'final_review']


def active_steps(project):
    return IMAGE_STEPS if project.get('output_type', 'video') == 'image' else STEPS


for _template in TEMPLATES:
    _template['output_type'] = 'video'
IMAGE_FORMATS = [
    ('portrait', 'Portrait', 'Create an expressive portrait with faithful identity.', '4:5', 'Face, expression and identity', 'Soft shaped portrait light', 'Identity, anatomy and expression are faithful.'),
    ('product', 'Product image', 'Show a faithful product with deliberate materials and reflections.', '1:1', 'Product silhouette and material detail', 'Controlled soft key and shaped reflections', 'Silhouette, materials, colour and markings match the actual product.'),
    ('thumbnail', 'Thumbnail', 'Make one readable visual promise at small viewing size.', '16:9', 'One focal subject with space for exact typography', 'Clear subject separation', 'The focal subject remains readable at thumbnail size.'),
    ('poster', 'Poster', 'Build a clear visual hierarchy for a poster or cover.', '2:3', 'Hero composition and deliberate text-safe space', 'Purposeful contrast and readable hierarchy', 'Composition supports the message and leaves usable text space.'),
    ('concept-art', 'Concept art', 'Explore a coherent world, character or environment design.', '16:9', 'Readable shapes, depth and design intent', 'Motivated world light', 'Shapes, perspective and materials support the intended design.'),
    ('social', 'Social image', 'Create a platform-aware social image with a clear message.', '1:1', 'Clear subject inside platform crop-safe areas', 'Readable light at mobile viewing size', 'The message and subject survive the intended mobile crop.'),
    ('custom', 'Custom image', 'Define your own still-image format and acceptance criteria.', '16:9', 'Intentional subject, perspective and depth', 'Light chosen for the image purpose', 'The image satisfies the creator-defined acceptance criteria.'),
]
TEMPLATES += [{'id': 'image-' + key, 'name': name, 'description': description, 'structure': [name + ' concept'], 'aspect': aspect, 'output_type': 'image'} for key, name, description, aspect, composition, lighting, check in IMAGE_FORMATS]
