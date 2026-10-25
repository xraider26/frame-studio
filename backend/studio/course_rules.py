"""Review-derived studio rules with explicitly scoped original-course citations."""
import copy
import hashlib
import json
from pathlib import Path
from .paths import resource_root

SOURCE_FILE = resource_root() / 'docs' / 'sources' / 'AI_Video_Course_Review_and_Workflow.md'
RULES = [
    ('brief', 'Establish the brief', 'Record the viewer promise, audience, format, runtime, references and resource limit.', 'Brief must name an opening and a payoff that can fit the selected duration.'),
    ('hook', 'Write and time the story', 'Choose a hook the ending actually pays off; each beat adds information or emotion.', 'Reject a hook that the planned ending does not deliver.'),
    ('timing', 'Write and time the story', 'Measure a scratch read, include pauses and recalculate beats for the actual runtime.', 'Do not reuse a fixed advertising timeline at a different duration.'),
    ('identity', 'Lock references and state', 'Check canonical views and maintain versioned character, costume, location and prop references.', 'Resolve real asset IDs and upload slots; names alone are not uploaded references.'),
    ('state', 'Lock references and state', 'Track mutable states such as held objects, door position, seats, clothes and emotion.', 'Explain any change between the prior ending state and the next opening state.'),
    ('light', 'Lock references and state', 'Track physical light sources; choose hard or soft light, colour and shadow depth, describe material response and derive direction per setup.', 'Do not paste camera-left across reverse angles as if it were a world-space light position.'),
    ('appearance', 'Design individual shot cards', 'Describe subject and layered environment, camera/composition, motivated light, shadow softness, material response, mood and optional style.', 'Concrete observable appearance takes precedence over strings of quality adjectives.'),
    ('motion', 'Design individual shot cards', 'Plan opening state, one primary action, one motivated camera move, ending state and timing.', 'Split dense actions, difficult transitions and multiple locations into separate shots.'),
    ('framing', 'Design individual shot cards', 'Use wide views for geography, medium views for gesture, close-ups for emotion and inserts for detail; choose viewpoint, depth and lead room for the story.', 'A locked camera is a valid choice; close facial performance usually needs simpler motion.'),
    ('capabilities', 'Check the actual Flow interface', 'Verify the selected generator mode, duration, aspect, audio, reference limits and cost.', 'Course-specific model settings are not proof of current provider support.'),
    ('iteration', 'Generate and retain evidence', 'Inspect a representative pilot; name the defect and change the smallest useful constraint.', 'Simplify or redesign after repeated failure instead of spending on blind retries.'),
    ('inspection', 'Quality gate', 'Watch the full clip and inspect beginning, middle and end for identity, anatomy, physics, light and audio.', 'A clean clip must still serve the story; returning a file is not a quality pass.'),
    ('edit', 'Edit, mix and package', 'Trim for the story; match colour; add purposeful ambience, foley, voice, music and readable captions.', 'Generated duration and retained edit duration are different; exact end-card text belongs in editing.'),
    ('final', 'Edit, mix and package', 'Inspect the actual final export at its intended viewing size, including transitions, captions and sound.', 'Selected shot media alone does not certify the final edited video.'),
    ('learning', 'Learn from the pilot', 'Record usable-shot cost, attempts, time and defects; change one major variable at a time.', 'Separate audience demand from execution quality; no invented retention or success metrics.'),
    ('claims', 'Original guide decisions', 'Use advertising structure without inventing evidence, endorsements or factual product claims.', 'Do not present a synthetic performer as an independent real customer.'),
    ('podcast', 'Original guide decisions', 'Keep assigned speakers, listener reactions, studio geography and reference identities coherent.', 'Only the intended speaker talks; carry speaker audio under silent listener cutaways.'),
    ('animation', 'Original guide decisions', 'Lock character design, visual metaphor, expression, costume and material rules.', 'Track emotional-weather and metaphor state across shots instead of resetting arbitrarily.'),
    ('clay', 'Original guide decisions', 'Keep handmade material, miniature scale, costume, product identity and tactile foley consistent.', 'Repair mismatched product references and impossible narration timing before generation.'),
]


VERIFIED_SOURCE_FILE = SOURCE_FILE.with_name('verified-course-lessons.json')


def verified_course_material():
    """Load the versioned paraphrase ledger; original private PDFs are never required."""
    return json.loads(VERIFIED_SOURCE_FILE.read_text(encoding='utf-8'))


def _citations(items):
    unique = {}
    for item in items:
        for citation in item.get('citations', []):
            unique[(citation['source_id'], citation['page'])] = citation
    return copy.deepcopy(list(unique.values()))


def source_rules(ids=None):
    selected = set(ids) if ids is not None else None
    material = verified_course_material()
    result = []
    for ident, section, teaching, correction in RULES:
        if selected is not None and ident not in selected:
            continue
        principles = [p for p in material['principles'] if ident in p['rule_ids']]
        corrections = [p for p in material['corrections'] if ident in p['rule_ids']]
        result.append({
            'id': ident, 'source_id': 'supplied-review-v1', 'section': section,
            'teaching': teaching, 'correction': correction, 'provenance': 'review_derived',
            'grounding': 'original_pages_verified' if principles else 'review_only',
            'citations': _citations(principles),
            'principle_ids': [p['id'] for p in principles],
            'correction_citations': _citations(corrections),
            'correction_ids': [p['id'] for p in corrections],
            'citation_scope': 'Citations support linked paraphrased principles; studio corrections and the complete rule are adaptations, not verbatim course instructions.',
        })
    return result


def course_coverage():
    material = verified_course_material()
    return {
        'source_id': 'supplied-review-v1', 'title': 'AI Video Course Review and Workflow',
        'file': 'docs/sources/AI_Video_Course_Review_and_Workflow.md',
        'sha256': hashlib.sha256(SOURCE_FILE.read_bytes()).hexdigest() if SOURCE_FILE.is_file() else None,
        'review_status': 'Supplied review/playbook imported; recovered original PDFs verified only on the pages listed in the source ledger. The review claim of 45 PDFs is not independently verified.',
        'rule_count': len(RULES), 'rules': source_rules(),
        'adaptation': 'Recipe shot roles, prompts, suggested timings and repair instructions are studio-authored applications of the cited principles and supplied review. Source intentions do not certify generator performance.',
        'coverage_status': material['coverage']['status'],
        'coverage': copy.deepcopy(material['coverage']),
        'source_ledger': 'docs/sources/verified-course-lessons.json',
        'page_numbering': material['page_numbering'],
        'verified_sources': copy.deepcopy(material['sources']),
        'verified_principles': copy.deepcopy(material['principles']),
        'verified_frameworks': copy.deepcopy(material['frameworks']),
        'source_corrections': copy.deepcopy(material['corrections']),
        'missing': ['Original guides and pages outside the listed verification scope',
                    'Video-only lesson content', 'Current provider capability validation',
                    'Real finished-video validation for each recipe'],
    }


def source_catalog(source_id=None, recipe_id=None, stage=None, role=None, detail='summary', include_provenance=False, offset=0, limit=20):
    from .store import StudioError
    if detail not in {'summary', 'full'}: raise StudioError('invalid_detail', 'Choose summary or full.')
    if offset < 0 or not 1 <= limit <= 100: raise StudioError('invalid_page', 'Use offset >= 0 and limit 1..100.')
    if recipe_id:
        from .recipes import recipe_catalog
        recipes = recipe_catalog(recipe_id, stage, role, 'full', include_provenance)
        rules = recipes[0]['source_rules'] if recipes else []
    else:
        rules = source_rules()
        if stage or role:
            raise StudioError('recipe_scope_required', 'Provide recipe_id to resolve stage/role applicability.')
    rules = [r for r in rules if source_id is None or r['id'] == source_id or r['source_id'] == source_id]
    rules = rules[offset:offset+limit]
    for rule in rules:
        if detail == 'summary':
            for key in list(rule):
                if key not in {'id', 'source_id', 'section', 'grounding', 'version', 'required', 'phase', 'stage', 'role_ids'}: rule.pop(key)
        elif not include_provenance:
            for key in ('citations', 'correction_citations', 'provenance', 'citation_scope'): rule.pop(key, None)
    return {'rules': rules, 'offset': offset, 'limit': limit}
