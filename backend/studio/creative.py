"""Validated creative records. Blank shot controls inherit; explicit values override."""
import copy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

Text = Annotated[str, StringConstraints(max_length=8000)]
Short = Annotated[str, StringConstraints(max_length=200)]
Seconds = Annotated[float, Field(ge=0, le=3600)]
Money = Annotated[float, Field(ge=0, le=1_000_000_000)]


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)


class Camera(Record):
    body_look: Text = ''
    lens: Text = ''
    aperture: Text = ''
    framing: Text = ''
    angle: Text = ''
    position: Text = ''
    foreground: Text = ''
    midground: Text = ''
    background: Text = ''
    lead_room: Text = ''
    screen_direction: Text = ''
    move: Text = ''
    speed: Text = ''
    start_framing: Text = ''
    end_framing: Text = ''
    move_timing: Text = ''


class Lighting(Record):
    technique: Text = ''
    world_source: Text = ''
    direction: Text = ''
    softness: Text = ''
    contrast: Text = ''
    temperature: Text = ''
    practicals: Text = ''
    material_response: Text = ''


class Art(Record):
    style: Text = ''
    palette: Text = ''
    materials: Text = ''
    texture: Text = ''


class TimedAction(Record):
    start: Seconds = 0
    end: Seconds = 0
    description: Text = ''


class Action(Record):
    opening: Text = ''
    primary_action: Text = ''
    ending: Text = ''
    beats: list[TimedAction] = Field(default_factory=list, max_length=100)
    state_before: dict[Short, Short] = Field(default_factory=dict, max_length=100)
    state_after: dict[Short, Short] = Field(default_factory=dict, max_length=100)
    transition: Text = ''
    continuity_from: Short = ''
    visible_entities: list[Short] = Field(default_factory=list, max_length=100)
    headcount: int | None = Field(default=None, ge=0, le=10000)


class Sound(Record):
    speaker_id: Short = ''
    dialogue: Text = ''
    voice: Text = ''
    measured_seconds: Seconds | None = None
    pauses_seconds: Seconds | None = None
    ambience: Text = ''
    foley: Text = ''
    music: Text = ''
    captions: Text = ''
    cutaway: bool | None = None


class Reference(Record):
    slot: Short
    asset_id: Short
    version: int = Field(default=1, ge=1, le=100000)
    role: Literal['character', 'location', 'prop', 'style', 'start_frame', 'end_frame', 'motion', 'mask'] = 'character'
    entity_id: Short = ''
    notes: Text = ''


class Quality(Record):
    criteria: list[Short] = Field(default_factory=list, max_length=50)
    known_defect: Text = ''
    revision_reason: Text = ''


class Editorial(Record):
    coverage_role: Short = ''
    purpose: Text = ''
    transition_in: Text = ''
    audio_source_shot_id: Short = ''
    audio_continuity: Text = ''


class Direction(Record):
    editorial: Editorial = Field(default_factory=Editorial)
    recipe_role: Short = ''
    decision_reason: Text = ''
    scene_id: Short = ''
    story_purpose: Text = ''
    script_beat: Text = ''
    environment: Text = ''
    mood: Text = ''
    generation_mode: Literal['inherit', 'text_to_video', 'image_to_video', 'start_end', 'motion_control'] = 'inherit'
    camera: Camera = Field(default_factory=Camera)
    lighting: Lighting = Field(default_factory=Lighting)
    art: Art = Field(default_factory=Art)
    action: Action = Field(default_factory=Action)
    sound: Sound = Field(default_factory=Sound)
    references: list[Reference] = Field(default_factory=list, max_length=100)
    quality: Quality = Field(default_factory=Quality)
    technique_ids: list[Short] = Field(default_factory=list, max_length=100)


class Brief(Record):
    premise: Text = ''
    promise: Text = ''
    niche: Text = ''
    opening: Text = ''
    payoff: Text = ''
    factual_requirements: Text = ''
    factual_sources: Text = ''


class StoryBeat(Record):
    id: Short
    title: Short = ''
    duration_seconds: Seconds = 0
    narration: Text = ''
    dialogue: Text = ''
    action: Text = ''
    captions: Text = ''
    measured_seconds: Seconds | None = None
    fact_or_dramatization: Text = ''


class Story(Record):
    sequence_id: Short = ''
    hooks: list[Short] = Field(default_factory=list, max_length=20)
    selected_hook: Text = ''
    framework: Text = ''
    beats: list[StoryBeat] = Field(default_factory=list, max_length=200)


class Entity(Record):
    id: Short
    kind: Literal['character', 'location', 'prop', 'style']
    name: Short
    version: int = Field(default=1, ge=1, le=100000)
    identity: Text = ''
    wardrobe: Text = ''
    voice: Text = ''
    layout: Text = ''
    light_sources: Text = ''
    materials: Text = ''
    asset_ids: list[Short] = Field(default_factory=list, max_length=50)


class Capabilities(Record):
    model: Short = ''
    confirmed: bool = False
    source: Text = ''
    observed_at: Short = ''
    modes: list[Short] = Field(default_factory=list, max_length=30)
    durations: list[Seconds] = Field(default_factory=list, max_length=50)
    aspects: list[Short] = Field(default_factory=list, max_length=20)
    max_references: int | None = Field(default=None, ge=0, le=1000)
    audio: bool | None = None


class Resources(Record):
    unit: Short = 'credits'
    limit: Money | None = None
    pilot_limit: Money | None = None
    max_attempts_per_shot: int | None = Field(default=None, ge=1, le=1000)
    image_cost: Money | None = None
    video_cost: Money | None = None
    cost_evidence: Text = ''


class Experiment(Record):
    id: Short
    variable: Text = ''
    hypothesis: Text = ''
    result: Text = ''
    source_date: Text = ''
    impressions: int | None = Field(default=None, ge=0)
    ctr_percent: float | None = Field(default=None, ge=0, le=100)
    completion_percent: float | None = Field(default=None, ge=0, le=100)


class RecipeSelection(Record):
    id: Short = ''
    version: int = Field(default=0, ge=0, le=100000)


class Production(Record):
    recipe: RecipeSelection = Field(default_factory=RecipeSelection)
    brief: Brief = Field(default_factory=Brief)
    story: Story = Field(default_factory=Story)
    bible: list[Entity] = Field(default_factory=list, max_length=200)
    defaults: Direction = Field(default_factory=Direction)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    resources: Resources = Field(default_factory=Resources)
    require_recorded_checks: bool = False
    format_rules: list[Short] = Field(default_factory=list, max_length=50)
    experiments: list[Experiment] = Field(default_factory=list, max_length=100)


FORMAT_RULES = {
    'ai-film': ['Motivate each camera move by what it reveals.', 'Lock identity, geography and object states across scenes.', 'Choose a deliberate opening and ending composition.'],
    'short-drama': ['Every beat changes the conflict or emotion.', 'Track staging, held objects and screen direction.', 'Time dialogue with a scratch read.'],
    'ugc': ['Deliver the hook promise through a visible demonstration.', 'Use restrained handheld movement and deliberate native contrast/saturation.', 'Keep product appearance consistent; identify dramatised testimony.'],
    'advertisement': ['Choose audience awareness and an honest benefit.', 'Record evidence for product claims.', 'Fit hook, demonstration and CTA to the actual runtime.'],
    'explainer': ['Each beat adds one clear idea.', 'Distinguish factual sources from illustration.', 'Use captions to clarify rather than duplicate dense narration.'],
    'podcast': ['Assign host and guest identities and seats.', 'Keep studio layout and physical light sources fixed.', 'Keep speaker audio continuous under listener cutaways; only the speaker talks.'],
    '2d-animation': ['Lock character silhouette, wardrobe and line/material rules.', 'Use a consistent visual metaphor.', 'Track expression and emotional-weather changes.'],
    'claymation': ['Use handmade materials and a consistent miniature scale.', 'Plan tactile action-synchronised foley.', 'Check costume, product and narration timing across shots.'],
    'custom': ['Choose a clear opening and payoff.', 'Define the acceptance criteria for your own format.'],
}


def default_production(template_id='custom'):
    looks = {
        'ugc': {'camera': {'body_look': 'Natural phone footage; restrained contrast and saturation', 'move': 'Subtle handheld', 'aperture': 'Moderately deep focus'}, 'lighting': {'technique': 'Soft motivated window light'}, 'art': {'style': 'Native creator realism'}},
        'podcast': {'camera': {'move': 'Locked off', 'framing': 'Medium close-up'}, 'lighting': {'technique': 'Soft studio key with motivated practicals'}},
        '2d-animation': {'art': {'style': 'Graphic 2D animation', 'materials': 'Consistent line weight, silhouette and flat colour'}},
        'claymation': {'art': {'style': 'Tactile claymation', 'materials': 'Hand-shaped clay in a consistent miniature set', 'texture': 'Subtle fingerprints and tool marks'}},
    }
    return Production(format_rules=FORMAT_RULES.get(template_id, ['Define subject, use, composition, light, style and required references.', 'Inspect actual image fidelity, anatomy, materials, crop and text constraints.'] if template_id.startswith('image-') else FORMAT_RULES['custom']), defaults=Direction.model_validate(looks.get(template_id, {}))).model_dump()


def merge(base, patch):
    if not isinstance(patch, dict):
        from .store import StudioError
        raise StudioError('invalid_creative_record', 'Nested creative updates must be objects; use blank fields to inherit.')
    result = copy.deepcopy(base)
    for key, value in patch.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) and isinstance(result.get(key), dict) else copy.deepcopy(value)
    return result


def validated(model, value):
    try:
        return model.model_validate(value).model_dump()
    except (ValidationError, TypeError) as exc:
        # Imported lazily to keep store migration free from circular imports.
        from .store import StudioError
        message = str(exc)[:1800]
        raise StudioError('invalid_creative_record', message) from exc


def normalize_direction(value):
    return validated(Direction, value)


def populated(value):
    if isinstance(value, dict):
        return {k: populated(v) for k, v in value.items() if v not in ('', None, [], {}, 'inherit')}
    return value


def effective_direction(project, shot):
    s = project['settings']
    base = Direction(camera=Camera(lens=s['lens'], framing=s['framing'], move=s['camera_move']),
                     lighting=Lighting(technique=s['lighting']), art=Art(style=(s.get('creative_intake') or {}).get('art_style') or s['style'], palette=s['palette']),
                     sound=Sound(ambience=s['sound'])).model_dump()
    base = merge(base, populated(project.get('production', {}).get('defaults', {})))
    result = merge(base, populated(shot.get('direction', {})))
    identity = project.get('shared_identity', {})
    locked = {e['id'] for e in identity.get('entities', [])}
    canonical = identity.get('references', [])
    relevant = set(result['action']['visible_entities']) | {result['sound']['speaker_id']} | {r.get('entity_id', '') for r in result['references']}
    relevant.discard('')
    if relevant:
        styles = {e['id'] for e in identity.get('entities', []) if e['kind'] == 'style'}
        canonical = [r for r in canonical if r['entity_id'] in relevant | styles]
    if canonical:
        result['references'] = [r for r in result['references'] if r.get('entity_id') not in locked or r.get('role') in ['start_frame', 'end_frame', 'motion', 'mask']]
        result['references'] += copy.deepcopy(canonical)
    return result


def creative_schema():
    return {'schema_version': 2, 'direction': Direction.model_json_schema(), 'production': Production.model_json_schema(),
            'inheritance': 'Blank controls inherit project values. Save custom overrides in shot.direction. Omitted direction is preserved for older clients.'}
