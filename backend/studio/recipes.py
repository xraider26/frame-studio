"""Versioned production recipes shared by UI, agents, compiler and quality review."""
import copy
import json
import math
import uuid
from pathlib import Path
from .course_rules import source_rules, course_coverage
from .paths import resource_root

VERSION = 1
STAGES = {
    'brief': ['State the idea, audience, viewer promise and intended emotion.', 'Agree the runtime, aspect, output tools, factual sources and pilot resource limit.'],
    'script': ['Choose a hook and payoff; separate visual action, narration, dialogue and captions.', 'Measure a scratch read and allocate retained edit beats to the actual runtime.'],
    'visual_direction': ['Prepare and inspect canonical characters, locations, props and material references.', 'Explain framing, movement and physical light choices for each shot purpose; compile appearance prompts with actual reference mappings.'],
    'pilot': ['Choose a representative shot with the hardest important identity, performance or interaction.', 'Verify real generator capabilities and costs, generate through authorized tools and inspect the full result before scaling.'],
    'production': ['Carry identity, world light, screen direction and before/after state across cuts.', 'Generate one primary action per dependable shot, inspect actual media and repair named defects within the user limits.'],
    'editor_handoff': ['Package chosen real media, source ranges, retained timing, transitions, sound and caption instructions.', 'Preserve speaker audio under cutaways; match colour and add exact graphics in the external editor.'],
    'final_review': ['Import the actual external final edit and inspect it at intended viewing size.', 'Record final picture, story, continuity, timing, captions, mix and packaging checks; attach model/settings scope and human observations.'],
}
DECISIONS = ['State the narrative or communication purpose of each shot.',
             'Explain how framing, depth, camera movement and light support that purpose.',
             'Adapt the recipe to the idea, measured performance and verified generator capabilities; do not copy a camera move into every shot.',
             'Keep user overrides; when they conflict with intent, report the conflict rather than silently replacing them.']
COMMON_FINAL = ['The opening promise is paid off by the ending.', 'Every retained shot contributes useful information or emotion.',
                'Identity, geography, objects, screen direction and light remain coherent across cuts.',
                'Runtime, framing and captions work at the intended viewing size.', 'Speech is intelligible; music, ambience and foley serve the scene.',
                'Transitions, colour and beginning/end feel deliberate; no accidental holds or broken edits remain.']


def role(ident, title, weight, purpose, camera, light, checks, sound, repair):
    return {'id': ident, 'title': title, 'weight': weight, 'purpose': purpose,
            'direction': {'camera': camera, 'lighting': light}, 'quality': checks,
            'sound': sound, 'repair': repair}


RECIPES = [
    {'id': 'ai-film', 'name': 'AI film', 'intent': 'Build a coherent cinematic world and pay off a visible discovery.',
     'rules': ['appearance', 'framing', 'motion', 'identity', 'state', 'light', 'edit'],
     'references': ['Canonical character views and intentional wardrobe variants', 'Location layout, practical lights and hero props', 'One coherent palette and visual treatment'],
     'planning': ['Design an establishing image, an informative discovery and a resolved closing composition.', 'Let the important reveal motivate camera movement; use a locked setup for difficult facial performance.'],
     'image_checks': ['Character, location and prop design match the approved references.', 'Depth layers and light make the story-critical subject readable.'],
     'video_checks': ['Opening and ending states support the planned edit.', 'Camera movement reveals story information without losing identity or geography.'],
     'roles': [role('establish', 'Establish the world', 3, 'Orient the viewer in the world and establish the story question.', {'framing': 'Wide environmental shot', 'lens': '24–35mm environmental feel', 'move': 'Locked off'}, {'technique': 'Motivated key with readable shadow detail'}, ['Location geography and the point of attention are clear.'], 'Location ambience establishes scale; music leaves room for the discovery.', 'Simplify the composition and camera; restore readable geography.'),
               role('discovery', 'Discovery', 4, 'Reveal the detail or decision that changes what the viewer understands.', {'framing': 'Medium or close shot', 'lens': '50–85mm intimate feel', 'move': 'Restrained push toward the revealed detail'}, {'technique': 'Motivated source isolates the discovery'}, ['The discovery is visible and changes the story.'], 'A precise foley cue or silence emphasizes the discovery.', 'Isolate one action and give the reveal a clearer start and end.'),
               role('payoff', 'Payoff', 3, 'Resolve the opening question through a deliberate ending image.', {'framing': 'Resolved medium or wide composition', 'move': 'Locked off'}, {'technique': 'Continue established world light'}, ['The ending visibly pays off the opening.'], 'Resolve the sound motif; leave clean handles for the final cut.', 'Replace drift with a held intentional end composition.')],
     'example_titles': ['Establish the world', 'Observatory discovery', 'Deliberate closing image']},
    {'id': 'ugc', 'name': 'UGC', 'intent': 'Make a natural creator demonstration clear, believable and useful.',
     'rules': ['hook', 'claims', 'timing', 'appearance', 'identity', 'inspection'],
     'references': ['Canonical creator and wardrobe', 'Product views, exact silhouette, colour and real demonstration constraints', 'Natural room and window-light reference'],
     'planning': ['Use a specific viewer problem and an observable demonstration.', 'Use phone-like framing, restrained handheld movement and moderate depth instead of generic cinematic treatment.'],
     'image_checks': ['Product appearance matches the approved reference.', 'Creator skin, hands and room feel natural and readable.'],
     'video_checks': ['Product appearance matches the approved reference.', 'The demonstration is legible and supports the stated takeaway.', 'Synthetic performance is not presented as independent real testimony.'],
     'roles': [role('hook', 'Creator hook', 2, 'Name or show a specific problem the demonstration will resolve.', {'body_look': 'Natural phone footage; restrained contrast and saturation', 'framing': 'Medium creator view', 'move': 'Subtle handheld', 'aperture': 'Moderately deep focus'}, {'technique': 'Soft motivated window light'}, ['The hook promise is specific and achievable.'], 'Conversational voice with a measured scratch read.', 'Shorten the hook and keep the camera stable enough to read the face.'),
               role('demonstration', 'Product demonstration', 5, 'Show one observable use or product interaction clearly.', {'framing': 'Medium or detail view with hands and product visible', 'move': 'Locked off'}, {'technique': 'Continue natural window light'}, ['Hand/product contact is plausible and the relevant feature is visible.'], 'Keep speech separate from action; use restrained action-synchronous foley.', 'Reduce to one interaction; restore the product reference and show the contact point.'),
               role('takeaway', 'Takeaway', 3, 'Complete the demonstration with a supported useful conclusion.', {'framing': 'Natural medium creator view', 'move': 'Subtle handheld'}, {'technique': 'Match the established daylight'}, ['The takeaway is supported by what the viewer actually saw.'], 'Leave enough space for the final spoken line and caption.', 'Remove unsupported claims and give the result a readable hold.')],
     'example_titles': ['Creator opening', 'Readable demonstration', 'Simple takeaway']},
    {'id': 'short-drama', 'name': 'Short drama', 'intent': 'Make a character conflict and emotional reversal readable across connected shots.',
     'rules': ['hook', 'timing', 'identity', 'state', 'light', 'framing', 'inspection'],
     'references': ['Character portraits, wardrobe and voice direction', 'Shared set layout, seats, eyelines, physical lights and held props'],
     'planning': ['Define what each character wants and what changes at the reversal.', 'Establish geography before close coverage; measure dialogue and track screen direction.'],
     'image_checks': ['Costume, props and light match the intended scene state.', 'Faces, eyelines and staging communicate the intended relationship.'],
     'video_checks': ['Performance and dialogue communicate the intended emotional change.', 'Seats, props, eyelines and screen direction remain coherent.'],
     'roles': [role('conflict', 'Conflict', 3, 'Establish the relationship and the obstacle between the characters.', {'framing': 'Medium-wide relationship shot', 'move': 'Locked off'}, {'technique': 'Motivated source with readable faces'}, ['Staging makes the conflict understandable.'], 'Measure each assigned line and preserve room tone.', 'Clarify blocking and simplify competing gestures.'),
               role('reaction', 'Reaction', 4, 'Let the important reaction change the emotional meaning.', {'framing': 'Close-up of the reacting character', 'lens': '85mm portrait feel', 'move': 'Locked off'}, {'technique': 'Continue physical light from the established set'}, ['The intended reaction is readable without exaggerated movement.'], 'Use a listening cutaway when useful; only the active speaker talks.', 'Reduce camera movement, isolate the reaction and recheck eyeline.'),
               role('reversal', 'Reversal', 3, 'Make the changed relationship visible through a decision or action.', {'framing': 'Medium shot showing the changed relationship', 'move': 'Locked off'}, {'technique': 'Match established sources'}, ['The final action earns the emotional reversal.'], 'Leave breathing room after the last line.', 'Show the decisive action clearly and repair object-state continuity.')],
     'example_titles': ['Conflict in the frame', 'Reaction beat', 'Visible emotional turn']},
    {'id': 'advertisement', 'name': 'Advertisement', 'intent': 'Turn a credible product benefit into a memorable, visually supported message.',
     'rules': ['brief', 'claims', 'hook', 'timing', 'appearance', 'identity', 'edit'],
     'references': ['Approved product views, materials, logo/text files for editing', 'Brand palette and factual evidence for each benefit'],
     'planning': ['Choose audience awareness and one supported benefit before the script.', 'Fit problem, demonstration and next action to the actual runtime; reserve exact typography for editing.'],
     'image_checks': ['Product silhouette, colour and materials match approved references.', 'Reflections and composition keep the product readable.'],
     'video_checks': ['The visual demonstration supports the advertised benefit.', 'No fabricated proof, endorsement or performance claim appears.'],
     'roles': [role('problem', 'Problem or desire', 3, 'Show the audience-relevant problem or desire without overclaiming.', {'framing': 'Clear medium context shot', 'move': 'Locked off'}, {'technique': 'Motivated light suited to the brand'}, ['The problem or desire is clear without unsupported claims.'], 'A concise hook fits the measured beat.', 'Focus on one relevant situation and remove invented evidence.'),
               role('benefit', 'Product benefit', 5, 'Demonstrate the approved benefit with faithful product appearance.', {'framing': 'Product detail with readable material and interaction', 'move': 'One restrained reveal'}, {'technique': 'Controlled soft key and shaped reflections'}, ['The important feature stays visible and physically coherent.'], 'Use tactile foley; narration describes only supported benefits.', 'Rebind product views; simplify reflections or interaction.'),
               role('cta', 'Brand finish', 2, 'Leave a clear product impression and one appropriate next action.', {'framing': 'Hero product composition with room for an edit-added end card', 'move': 'Locked off'}, {'technique': 'Consistent brand lighting'}, ['The product is recognizable and the end-card area is usable.'], 'Allow a clear voice/caption finish; add exact text in editing.', 'Use a clean held product view; move precise typography to the editor.')],
     'example_titles': ['Audience context', 'Material and benefit', 'Product hero']},
    {'id': 'explainer', 'name': 'Explainer', 'intent': 'Help the viewer understand one idea through a clear sequence and useful example.',
     'rules': ['brief', 'hook', 'timing', 'claims', 'appearance', 'edit'],
     'references': ['Factual sources and approved terminology', 'Consistent visual metaphor, palette and illustrative assets'],
     'planning': ['Separate verified facts from visual analogy.', 'Teach one new idea per beat; simplify visuals before adding narration or captions.'],
     'image_checks': ['The visual metaphor is clear and internally consistent.', 'Illustration is distinguishable from factual evidence.'],
     'video_checks': ['Each beat adds one understandable idea.', 'Narration, visuals and captions agree without overwhelming the viewer.'],
     'roles': [role('question', 'Question', 2, 'Show the concrete question the explanation will answer.', {'framing': 'Simple wide or medium illustrative setup', 'move': 'Locked off'}, {'technique': 'Clear soft illumination'}, ['The question is visible or easy to state in one sentence.'], 'One concise question with space to understand the image.', 'Remove decorative objects and make the question concrete.'),
               role('mechanism', 'Explanation', 5, 'Reveal the mechanism through one understandable visual change.', {'framing': 'Readable detail or overhead view', 'move': 'Locked off'}, {'technique': 'Even illumination with subject separation'}, ['The mechanism and order of events are unambiguous.'], 'Align narration timing with the visible change.', 'Split the mechanism into simpler beats; verify the source claim.'),
               role('example', 'Example and takeaway', 3, 'Apply the explanation to a recognizable situation.', {'framing': 'Medium view that relates the example to the opening', 'move': 'Locked off'}, {'technique': 'Match the explanatory treatment'}, ['The example demonstrates the promised explanation.'], 'Summarize without adding an unexplained new claim.', 'Reuse the established metaphor and show the consequence clearly.')],
     'example_titles': ['A clear question', 'Show the mechanism', 'Apply the idea']},
    {'id': 'podcast', 'name': 'Podcast', 'intent': 'Present a coherent conversation with credible performance and stable studio geography.',
     'rules': ['podcast', 'identity', 'light', 'state', 'timing', 'edit'],
     'references': ['Separate host and guest identities, voices and wardrobe', 'Assigned seats, microphones, studio layout and fixed practical lights'],
     'planning': ['Map who speaks and who listens in every beat.', 'Record dialogue timing; plan listener cutaways while preserving the speaker audio.'],
     'image_checks': ['Host/guest identities, microphone placement and assigned seats are correct.', 'Studio light and layout agree across angles.'],
     'video_checks': ['Only the assigned speaker talks; the listener reacts silently.', 'Speaker audio and lip sync agree; microphones and eyelines remain stable.'],
     'roles': [role('opening', 'Opening thought', 3, 'Establish the speaker and a specific conversation topic.', {'framing': 'Medium studio portrait', 'move': 'Locked off'}, {'technique': 'Soft studio key with motivated practicals'}, ['The assigned speaker and seat are unmistakable.'], 'Measured conversational speech; controlled room tone.', 'Use one speaker and simplify the opening line.'),
               role('discussion', 'Discussion', 5, 'Develop the idea with readable speaker and listener coverage.', {'framing': 'Speaker medium close-up or silent listener cutaway', 'move': 'Locked off'}, {'technique': 'Match fixed studio lights'}, ['Listener cutaways retain the actual speaker audio.'], 'Carry speaker dialogue continuously under silent reactions.', 'Repair speaker assignment and lip sync; restore seat and eyeline.'),
               role('closing', 'Closing point', 2, 'Deliver a concise conclusion without resetting the set.', {'framing': 'Medium close-up on the concluding speaker', 'move': 'Locked off'}, {'technique': 'Continue the same studio sources'}, ['The concluding thought resolves the opening topic.'], 'Finish the last sentence with clean room tone handles.', 'Shorten the final line and hold the reaction for the cut.')],
     'example_titles': ['Host opening', 'Guest response', 'Listener cutaway']},
    {'id': '2d-animation', 'name': '2D animation', 'intent': 'Express a clear story through consistent graphic character design and visual metaphor.',
     'rules': ['animation', 'identity', 'hook', 'motion', 'state', 'edit'],
     'references': ['Canonical character silhouette, expressions and wardrobe', 'Locked palette, line weight, shape language and metaphor states'],
     'planning': ['Choose a coherent visual metaphor and show its change intentionally.', 'Keep character design and expression states stable through the sequence.'],
     'image_checks': ['Silhouette, line weight, costume and palette match the approved design.', 'The visual metaphor reads clearly.'],
     'video_checks': ['Character design and material treatment stay consistent during motion.', 'Expression and metaphor changes follow the planned story state.'],
     'roles': [role('establish', 'Establish', 3, 'Introduce the character and the visual metaphor.', {'framing': 'Simple medium-wide graphic composition', 'move': 'Locked off'}, {'technique': 'Consistent illustrative value separation'}, ['The character silhouette and metaphor are recognizable.'], 'A short sound motif introduces the visual idea.', 'Simplify shapes and reapply canonical line and colour rules.'),
               role('change', 'Animate the change', 4, 'Show one expressive action that changes the metaphor.', {'framing': 'Readable medium action view', 'move': 'Locked off'}, {'technique': 'Maintain the established graphic values'}, ['The action has a clear opening and ending expression state.'], 'Use one synchronized sound cue rather than dense narration.', 'Separate competing actions and restore expression continuity.'),
               role('resolve', 'Resolve', 3, 'Resolve the metaphor with a clear emotional payoff.', {'framing': 'Deliberate final illustrative composition', 'move': 'Locked off'}, {'technique': 'Preserve the palette; intentional mood change only'}, ['The metaphor resolves without an unexplained design reset.'], 'Resolve the motif and leave room for the final beat.', 'Restore the prior state and show the intended transformation clearly.')],
     'example_titles': ['Introduce the metaphor', 'Expressive change', 'Resolve the feeling']},
    {'id': 'claymation', 'name': 'Claymation', 'intent': 'Tell a tactile miniature story with coherent handmade materials and purposeful physical action.',
     'rules': ['clay', 'identity', 'motion', 'state', 'timing', 'edit'],
     'references': ['Character turnarounds, costumes and hero props', 'Miniature scale, clay texture, set materials and tactile sound references'],
     'planning': ['Design one readable physical action per shot at a stable miniature scale.', 'Plan tactile foley and measured narration; keep product/costume references consistent.'],
     'image_checks': ['Clay texture, miniature scale, wardrobe and prop design are consistent.', 'Handmade surfaces stay intentional and readable.'],
     'video_checks': ['Physical contact and object states remain plausible at miniature scale.', 'Foley follows the actual tactile action and narration fits the edit.'],
     'roles': [role('introduce', 'Introduce', 3, 'Establish the miniature character, material and practical situation.', {'framing': 'Medium-wide view at miniature eye level', 'move': 'Locked off'}, {'technique': 'Soft tabletop key with readable contact shadows'}, ['The material and miniature scale are coherent.'], 'Use small-scale room tone and a restrained tactile cue.', 'Restore scale and simplify competing surface textures.'),
               role('action', 'Tactile action', 4, 'Show one purposeful handmade interaction.', {'framing': 'Detail or medium view including the contact point', 'move': 'Locked off'}, {'technique': 'Maintain the same tabletop source'}, ['Hands and props make plausible contact without material drift.'], 'Plan precise clay, wood or fabric foley for the visible contact.', 'Split the action and rebind the canonical prop/material reference.'),
               role('reaction', 'Reaction', 3, 'Show a clear reaction and retain the changed object state.', {'framing': 'Readable character reaction with changed prop visible', 'move': 'Locked off'}, {'technique': 'Continue miniature set illumination'}, ['The reaction preserves the action outcome and costume.'], 'A short tactile finish leaves a clean edit handle.', 'Restore the ending prop state and hold the expression for the payoff.')],
     'example_titles': ['The miniature world', 'Tactile action', 'Character reaction']},
    {'id': 'custom', 'name': 'Custom', 'intent': 'Define an original creative treatment while preserving explicit production and quality standards.',
     'rules': ['brief', 'appearance', 'motion', 'identity', 'inspection', 'final', 'learning'],
     'references': ['Creator-defined identity, world, style and performance references'],
     'planning': ['Define the intended feeling, visual treatment and acceptance criteria in your own words.', 'Replace any suggested role or look deliberately; preserve timing, reference, review and resource discipline.'],
     'image_checks': ['The image matches the creator-defined visual intention and reference set.'],
     'video_checks': ['The performance and motion meet the creator-defined acceptance criteria.'],
     'roles': [role('opening', 'Opening', 3, 'Establish the creator-defined promise or point of attention.', {}, {}, ['The opening communicates the intended promise.'], 'Choose an intentional opening sound or silence.', 'Clarify the intended effect and simplify competing directions.'),
               role('development', 'Development', 4, 'Develop the idea through one meaningful change.', {}, {}, ['The development adds information or emotion.'], 'Align sound with the intended change.', 'Name the failed intention and revise one relevant constraint.'),
               role('closing', 'Closing', 3, 'Complete the idea with an intentional ending.', {}, {}, ['The ending resolves the creator-defined promise.'], 'Choose a deliberate ending and clean edit handles.', 'Make the payoff observable and review the final composition.')],
     'example_titles': ['Architectural study', 'Surreal botanical world', 'Documentary portrait']},
]


def recipe_by_id(ident):
    found = next((r for r in RECIPES if r['id'] == ident), None)
    if not found:
        from .store import StudioError
        raise StudioError('invalid_recipe', 'Choose an available production recipe.')
    r = copy.deepcopy(found)
    r.update(version=VERSION, stages=copy.deepcopy(STAGES), decision_requirements=list(DECISIONS),
             final_checks=list(COMMON_FINAL), validation_status='not_video_validated',
             source_rules=source_rules(list(dict.fromkeys(['brief', 'hook', 'timing', 'capabilities', 'iteration', 'inspection', 'final', 'learning'] + r['rules']))),
             examples=[{'id': f'{ident}-{n}', 'title': title, 'image': f'/recipe-examples/{ident}-{n}.png',
                        'kind': 'illustrative_ai_still', 'video_validated': False} for n, title in enumerate(r['example_titles'], 1)])
    r['stages']['brief'].append(r['intent'])
    r['stages']['script'] += r['planning']
    r['stages']['visual_direction'] += ['Prepare: ' + v for v in r['references']] + ['Inspect: ' + v for v in r['image_checks']]
    r['stages']['production'] += ['Inspect: ' + v for v in r['video_checks']]
    r['stages']['editor_handoff'] += [v['title'] + ': ' + v['sound'] for v in r['roles']]
    manifest = resource_root() / 'frontend' / 'public' / 'recipe-examples' / 'manifest.json'
    examples = {v['id']: v for v in json.loads(manifest.read_text(encoding='utf-8'))['examples']} if manifest.is_file() else {}
    for example in r['examples']:
        recorded = examples.get(example['id'], {})
        example.update(prompt=recorded.get('prompt', ''), why=recorded.get('why', ''),
                       available=bool(recorded) and (manifest.parent / (example['id'] + '.png')).is_file())
    return r


def recipe_catalog():
    return [recipe_by_id(r['id']) for r in RECIPES]


def recipe_context(p, shot=None):
    selected = p['production'].get('recipe', {})
    if not selected or not selected.get('id'):
        return {'active': False, 'message': 'Existing project: activate a recipe explicitly to use its standards.'}
    if selected.get('version') != VERSION or selected.get('id') != p['template_id']:
        return {'active': False, 'message': 'Recipe ID/version needs explicit migration before use.'}
    r = recipe_by_id(selected['id'])
    result = {'active': True, **r, 'coverage': course_coverage(), 'project_intent': p['production']['brief'],
              'stage_instructions': r['stages'], 'settings_scope': {'video_profile': p['settings']['video_generator'],
              'image_profile': p['settings']['image_generator'], 'capabilities': p['production']['capabilities']},
              'guidance': 'These are directing and inspection requirements, not proof the generator obeyed them. Keep human policy and budget limits.'}
    if shot:
        role_id = shot['direction'].get('recipe_role', '')
        result['shot_role'] = next((v for v in r['roles'] if v['id'] == role_id), None)
    return result


def recipe_criteria(p, shot, kind):
    context = recipe_context(p, shot)
    if not context['active']:
        return []
    checks = context['image_checks'] if kind == 'image' else context['video_checks']
    role_data = context.get('shot_role')
    return list(dict.fromkeys(checks + (role_data['quality'] if role_data and kind == 'video' else [])))


def seed_recipe(p, preserve=True):
    r = recipe_by_id(p['template_id'])
    p['production']['recipe'] = {'id': r['id'], 'version': VERSION}
    if not preserve:
        p['production']['require_recorded_checks'] = True
    total_weight = sum(v['weight'] for v in r['roles'])
    runtime = p['settings']['duration_seconds']
    allocated = [int(runtime * v['weight'] / total_weight) for v in r['roles']]
    for i in range(int(runtime) - sum(allocated)):
        allocated[i % len(allocated)] += 1
    for i, shot in enumerate(p['shots']):
        data = r['roles'][i] if len(p['shots']) == len(r['roles']) else None
        if not data:
            continue
        d = shot['direction']
        if not d.get('recipe_role'):
            d['recipe_role'] = data['id']
        if not d['story_purpose']:
            d['story_purpose'] = data['purpose']
        if not d.get('decision_reason'):
            d['decision_reason'] = 'Suggested recipe direction; adapt to the idea and explain any changed choices.'
        if not preserve:
            seconds = allocated[i]
            shot.update(duration_seconds=seconds, edit_duration_seconds=seconds)
            d['camera'].update(data['direction']['camera'])
            d['lighting'].update(data['direction']['lighting'])
            d['sound']['ambience'] = data['sound']


def retime_seeded_shots(p):
    """Only for a fresh settings-only recipe: split placeholder beats to valid clip lengths."""
    r = recipe_by_id(p['template_id'])
    if len(p['shots']) != len(r['roles']):
        return
    weight = sum(v['weight'] for v in r['roles'])
    result = []
    for shot, data in zip(p['shots'], r['roles']):
        remaining = p['settings']['duration_seconds'] * data['weight'] / weight
        part = 0
        while remaining > .000001:
            retained = min(30, remaining)
            new = copy.deepcopy(shot)
            if part:
                new['id'] = uuid.uuid4().hex
            if p['settings']['duration_seconds'] * data['weight'] / weight > 30:
                new['title'] += f' · part {part + 1}'
            new.update(duration_seconds=max(1, math.ceil(retained)), edit_duration_seconds=retained)
            result.append(new)
            remaining -= retained
            part += 1
    p['shots'] = result
