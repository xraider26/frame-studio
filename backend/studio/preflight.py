"""Deterministic production checks. Warnings are not semantic or visual inspection."""
from .creative import effective_direction
from pathlib import Path


def references_for(project, shot, kind):
    bindings = effective_direction(project, shot)['references']
    assets = {a['id']: a for a in project['assets']}
    if bindings:
        refs = [{**assets[r['asset_id']], 'slot': r['slot'], 'binding_role': r['role'], 'version': r['version'], 'entity_id': r['entity_id']} for r in bindings if r['asset_id'] in assets]
    else:
        refs = [{**a, 'slot': f'reference_{i}', 'version': a.get('version', 1)} for i, a in enumerate(project['assets'], 1)
                if a.get('role') == 'reference' and a['kind'] == 'image' and not a.get('source_video')
                and not (a.get('canonical_batch') and project.get('shared_identity'))]
    if kind == 'image':
        refs = [r for r in refs if r.get('binding_role') != 'motion' and r['kind'] == 'image']
    if kind == 'video' and shot.get('image_asset') and not any(r.get('binding_role') == 'start_frame' for r in refs):
        asset = assets.get(shot['image_asset'])
        if asset:
            refs.append({**asset, 'slot': 'keyframe', 'binding_role': 'start_frame', 'version': asset.get('version', 1)})
    return refs


def preflight(project, shot_id=None, kind=None):
    issues = []
    def issue(rule, severity, shot, path, message):
        issues.append({'rule': rule, 'severity': severity, 'shot_id': shot.get('id') if shot else None, 'path': path, 'message': message})
    production = project['production']
    selection = production.get('recipe', {})
    if selection.get('id'):
        from .recipes import recipe_context
        if not recipe_context(project)['active']:
            issue('recipe_version', 'error', None, 'production.recipe', 'Recipe ID/version is unavailable. Explicitly activate the current recipe in the studio before generation.')
    caps = production['capabilities']
    assets = {a['id']: a for a in project['assets']}
    entities = {e['id']: e for e in production['bible']}
    shots = project['shots']
    for i, shot in enumerate(shots):
        if shot_id and shot['id'] != shot_id:
            continue
        d = effective_direction(project, shot)
        action, sound = d['action'], d['sound']
        if selection.get('id') and (not d.get('story_purpose') or not d.get('decision_reason')):
            issue('recipe_decision', 'warning', shot, 'direction.decision_reason', 'Explain the shot purpose and how camera/light choices serve it; recipe defaults are suggestions.')
        duration = shot['duration_seconds']
        retained = shot.get('edit_duration_seconds', duration)
        if retained + shot.get('edit_in_seconds', 0) > duration:
            issue('edit_exceeds_generation', 'error', shot, 'edit_duration_seconds', 'Retained edit duration exceeds generation duration. Shorten the edit or extend the generation.')
        for n, beat in enumerate(action['beats']):
            if beat['end'] <= beat['start'] or beat['end'] > duration:
                issue('action_timing', 'error', shot, f'direction.action.beats.{n}', 'Action beats need end > start and must fit inside the generated clip.')
        if sound['measured_seconds'] is not None and sound['measured_seconds'] + (sound['pauses_seconds'] or 0) > min(retained, duration):
            issue('dialogue_timing', 'error', shot, 'direction.sound.measured_seconds', 'Measured speech plus pauses exceeds the retained edit. Split or retime this shot.')
        if (sound['dialogue'] or shot.get('narration')) and sound['measured_seconds'] is None:
            issue('unmeasured_dialogue', 'warning', shot, 'direction.sound.measured_seconds', 'Make a scratch read and record actual speaking time; no measured duration is recorded.')
        slots = set()
        for n, ref in enumerate(d['references']):
            path = f'direction.references.{n}'
            asset = assets.get(ref['asset_id'])
            expected_kind = 'video' if ref['role'] == 'motion' else 'image'
            if not asset or asset['kind'] != expected_kind or (asset.get('stale') and (asset.get('role') != 'reference' or asset.get('source_video'))):
                issue('reference_missing', 'error', shot, path, f"Reference {ref['asset_id']} does not resolve to a current {expected_kind}. Import or rebind the actual file.")
            elif not Path(asset.get('path', '')).is_file():
                issue('reference_file_missing', 'error', shot, path, 'The registered reference file is missing from disk. Reimport the actual file.')
            elif ref['version'] != asset.get('version', 1):
                issue('reference_version', 'error', shot, path, 'Reference version does not match the immutable asset version.')
            if ref['role'] == 'motion' and not ref['notes'].strip():
                issue('motion_compatibility_notes', 'error', shot, path, 'Record how the motion source matches the target pose and framing.')
            slot = ref['slot'].casefold()
            if not slot or slot in slots:
                issue('reference_slot', 'error', shot, path, 'Use a distinct, nonempty upload slot for each reference.')
            slots.add(slot)
            if ref['entity_id'] and ref['entity_id'] not in entities:
                issue('entity_missing', 'error', shot, path, 'Reference binding names a missing bible entity.')
        for entity in action['visible_entities'] + ([sound['speaker_id']] if sound['speaker_id'] else []):
            if entity not in entities:
                issue('entity_missing', 'error', shot, 'direction.action.visible_entities', f'Bible entity {entity} is missing. Add it or correct the ID.')
        if action['headcount'] is not None:
            character_count = sum(entities.get(e, {}).get('kind') == 'character' for e in action['visible_entities'])
            if character_count != action['headcount']:
                issue('headcount', 'warning', shot, 'direction.action.headcount', 'Visible character IDs and stated headcount disagree. Check who is in frame.')
        source_id = action['continuity_from']
        previous = next((s for s in shots[:i] if s['id'] == source_id), None) if source_id else (shots[i - 1] if i and d['scene_id'] and shots[i - 1]['direction']['scene_id'] == d['scene_id'] else None)
        if source_id and not previous:
            issue('continuation_source', 'error', shot, 'direction.action.continuity_from', 'Continuation must refer to an earlier shot in this project; cycles/forward links are unsupported.')
        if previous and not action['transition']:
            prior = effective_direction(project, previous)
            for key, value in action['state_before'].items():
                if key in prior['action']['state_after'] and prior['action']['state_after'][key] != value:
                    issue('continuity_state', 'warning', shot, 'direction.action.state_before.' + key, f'{key} changes from {prior["action"]["state_after"][key]} to {value}. Explain the transition or reconcile state.')
            if prior['lighting']['world_source'] and d['lighting']['world_source'] and prior['lighting']['world_source'] != d['lighting']['world_source']:
                issue('world_light', 'warning', shot, 'direction.lighting.world_source', 'Physical light source changes in a continuing setup. Check world-space placement or explain the transition.')
        mode = d['generation_mode']
        if mode == 'inherit':
            mode = 'image_to_video' if project['settings']['video_generator'] == 'runway_i2v' else 'text_to_video'
        if kind != 'image':
            roles = {r['role'] for r in d['references']}
            if mode in ['image_to_video', 'start_end'] and not shot['image_asset'] and 'start_frame' not in roles:
                issue('start_frame_missing', 'error', shot, 'direction.references', 'This mode needs an actual start image. Return a keyframe or bind a start-frame reference.')
            if mode == 'start_end' and 'end_frame' not in roles:
                issue('end_frame_missing', 'error', shot, 'direction.references', 'Start/end mode needs a bound end-frame image.')
            if mode == 'motion_control' and 'motion' not in roles:
                issue('motion_reference_missing', 'error', shot, 'direction.references', 'Bind the motion-source reference and record compatible pose/framing notes.')
            if caps['confirmed']:
                if caps['modes'] and mode not in caps['modes']:
                    issue('unsupported_mode', 'error', shot, 'direction.generation_mode', 'Selected mode is not among the recorded supported generator modes.')
                if caps['durations'] and duration not in caps['durations']:
                    issue('unsupported_duration', 'error', shot, 'duration_seconds', 'Choose a duration supported by the recorded model observation.')
        if caps['confirmed']:
            if not caps['source'] or not caps['observed_at'] or not caps['model']:
                issue('capability_evidence', 'error', shot, 'production.capabilities', 'Confirmed capabilities require model, observation source and date.')
            if caps['aspects'] and project['settings']['aspect_ratio'] not in caps['aspects']:
                issue('unsupported_aspect', 'error', shot, 'settings.aspect_ratio', 'Selected aspect ratio is outside the recorded generator capabilities.')
            count = len(references_for(project, shot, kind))
            if caps['max_references'] is not None and count > caps['max_references']:
                issue('reference_count', 'error', shot, 'direction.references', 'Bound reference count exceeds the recorded generator limit.')
        if len(action['beats']) > 3:
            issue('dense_action', 'warning', shot, 'direction.action.beats', 'Several action beats may overload one clip. Consider splitting into editable shots (heuristic).')
    if not caps['confirmed']:
        issue('capabilities_unverified', 'warning', None, 'production.capabilities', 'Model capabilities are not confirmed. Check the actual generator before spending.')
    total = sum(s.get('edit_duration_seconds', s['duration_seconds']) for s in shots)
    if abs(total - project['settings']['duration_seconds']) > .1:
        issue('runtime_total', 'warning', None, 'shots', f'Retained edits total {total:g}s; target is {project["settings"]["duration_seconds"]}s. Recalculate the story timeline.')
    beats = production['story']['beats']
    if beats and abs(sum(b['duration_seconds'] for b in beats) - project['settings']['duration_seconds']) > .1:
        issue('story_runtime', 'warning', None, 'production.story.beats', 'Story beat durations do not sum to target runtime.')
    return {'issues': issues, 'errors': sum(i['severity'] == 'error' for i in issues),
            'warnings': sum(i['severity'] == 'warning' for i in issues), 'retained_seconds': total,
            'scope': 'Deterministic planning checks only. Inspect actual media for artistic and visual/audio defects.'}
