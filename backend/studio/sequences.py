"""Editorial coverage plans, never an internal timeline renderer or generation job."""
import copy
import math
import uuid
from .creative import Direction
from .store import StudioError


def coverage(ident, title, purpose, weight=1, transition='Cut', audio='Use the intended on-screen audio.', source=None, kind=None):
    value = {'id': ident, 'title': title, 'coverage_role': kind or ident, 'purpose': purpose, 'weight': weight, 'transition_in': transition, 'audio_continuity': audio}
    if source: value['source_role_id'] = source
    return value


SEQUENCES = [
    {'id': 'creator-explainer', 'name': 'Creator explainer', 'description': 'A-roll establishes the thought; B-roll illustrates it before returning to the creator.', 'roles': [
        coverage('a-roll-open','Creator opening','State the viewer question.',2,kind='a-roll'),
        coverage('b-roll','Illustrating B-roll','Show the example while preserving creator speech.',3,'L-cut: carry creator audio under B-roll','Preserve the opening creator audio; do not regenerate duplicate dialogue.','a-roll-open'),
        coverage('a-roll-close','Creator conclusion','Return to the speaker and complete the thought.',2,'J-cut: next line may begin before the return',kind='a-roll')]},
    {'id': 'podcast-conversation', 'name': 'Podcast conversation', 'description': 'Master, host, guest and listening coverage with coherent seats and eyelines.', 'roles': [
        coverage('master','Conversation master','Establish speakers, seats and room geography.'),
        coverage('host','Host coverage','Show the host asking the question.',2), coverage('guest','Guest coverage','Show the guest answer.',3),
        coverage('reaction','Listener reaction','Show listening while retaining guest audio.',1,'L-cut to listener','Retain guest speech and room tone.','guest')]},
    {'id': 'interview-doc', 'name': 'Documentary interview', 'description': 'Answer, illustrative insert and a listening reaction preserve interview meaning.', 'roles': [
        coverage('answer','Interview answer','Present the interview answer.',3),
        coverage('insert','Context insert','Illustrate the answer with verified context.',2,'L-cut','Keep interview answer audio continuous.','answer',kind='b-roll'),
        coverage('reaction','Listening reaction','Allow the answer to land.',1,'L-cut','Keep the answer and room tone continuous.','answer')]},
    {'id': 'product-demo', 'name': 'Product demonstration', 'description': 'A hook leads into an observable demonstration, useful detail and supported payoff.', 'roles': [
        coverage('hook','Product hook','Show a relevant viewer need.'),coverage('demonstration','Demonstration','Show one observable product interaction.',3,'Cut on action'),
        coverage('detail','Product detail','Show the useful feature clearly.',2,'Match action; preserve object state'),coverage('payoff','Supported payoff','Pay off only what the demonstration supports.')]},
    {'id': 'short-drama', 'name': 'Short drama coverage', 'description': 'Establish geography, exchange coverage and an emotional change.', 'roles': [
        coverage('establish','Establish geography','Show the relationship, positions and screen direction.'),coverage('shot-reverse','Shot / reverse shot','Cover the exchange with matching eyelines.',3,'Motivated reverse angle'),
        coverage('reaction','Reaction','Let a listening response change the meaning.',2,'L-cut where useful','Preserve the active speaker audio.','shot-reverse'),coverage('payoff','Dramatic payoff','Make the changed relationship visible.')]},
    {'id': 'montage', 'name': 'Montage', 'description': 'Connected visual beats build a progression through purposeful rhythm.', 'roles': [
        coverage('establish','Montage opening','Establish the motif.'),coverage('progression','Visual progression','Advance one clear change.',2,'Match cut where motivated','Carry a deliberate ambience or music bed.','establish'),coverage('resolution','Montage resolution','Resolve the visual motif.',1,'Rhythmic cut','Continue the chosen audio bed.','establish')]},
    {'id': 'hook-reveal-payoff', 'name': 'Hook, reveal, payoff', 'description': 'A compact visual question, informative reveal and earned ending.', 'roles': [
        coverage('hook','Hook','Make a specific visual promise.'),coverage('reveal','Reveal','Reveal the information that answers the hook.',2,'Cut on action where useful'),coverage('payoff','Payoff','Deliver a readable earned ending.')]},
]
for sequence in SEQUENCES:
    sequence['technique_notes'] = ['A-roll carries the primary speaker or action; B-roll adds relevant context.', 'J-cuts and L-cuts are external editor instructions, not generated timeline operations. Preserve intended source speech and room tone.', 'Cut on action or use a match cut only when motivated; track screen direction, eyelines and object state.']


def sequence_catalog():
    return {'sequences': copy.deepcopy(SEQUENCES), 'planning_only': True}


def sequence_by_id(ident):
    item = next((s for s in SEQUENCES if s['id'] == ident), None)
    if not item: raise StudioError('invalid_sequence', 'Choose an available sequence pattern.')
    return copy.deepcopy(item)


def sequence_context(p):
    ident = p['production']['story'].get('sequence_id', '')
    return sequence_by_id(ident) if any(s['id'] == ident for s in SEQUENCES) else None


def has_work(p):
    from .recipes import seed_recipe
    from .templates import TEMPLATES, DEFAULT_SETTINGS
    baseline = copy.deepcopy(p)
    baseline['settings']['duration_seconds'] = DEFAULT_SETTINGS['duration_seconds']
    for shot in baseline['shots']:
        shot['direction'] = Direction().model_dump()
    seed_recipe(baseline, preserve=False)
    template = next((t for t in TEMPLATES if t['id'] == p['template_id']), None)
    titles = template['structure'] if template else []
    shots = 0
    for i, (shot, placeholder) in enumerate(zip(p['shots'], baseline['shots'])):
        if (shot.get('image_prompt') or shot.get('motion_prompt') or shot.get('narration') or
                shot['direction'] != placeholder['direction'] or shot.get('edit_in_seconds', 0) != 0 or
                shot['duration_seconds'] != placeholder['duration_seconds'] or shot['edit_duration_seconds'] != placeholder['edit_duration_seconds'] or i >= len(titles) or shot['title'] != titles[i]):
            shots += 1
    story = p['production']['story']
    if any(story.values()) or 'story' in p.get('template_source', {}).get('sections', []):
        shots = max(shots, 1)
    return {'shots': shots, 'assets': len(p['assets']), 'documents': sum(bool(v.get('text')) for v in p['documents'].values())}


def plan(p, sequence):
    if p.get('output_type','video') != 'video': raise StudioError('invalid_output_type', 'Sequence patterns require a video project. Choose an image template for still images.')
    runtime = float(p['settings']['duration_seconds'])
    roles = sequence['roles']; total = sum(r['weight'] for r in roles)
    if runtime < len(roles): raise StudioError('sequence_runtime_too_short', f'This sequence needs at least {len(roles)} seconds: one second per coverage role. Increase runtime or choose a simpler pattern.')
    # Reserve one second for each role before distributing the remainder by weight.
    durations = [1 + (runtime-len(roles))*r['weight']/total for r in roles]
    result=[]; source_ids={}
    for role, duration in zip(roles,durations):
        count=math.ceil(duration/30); retained=duration/count
        for part in range(count):
            ident=uuid.uuid4().hex; source_ids.setdefault(role['id'],ident)
            direction=Direction().model_dump(); direction['story_purpose']=role['purpose']
            direction['editorial'].update(coverage_role=role['coverage_role'],purpose=role['purpose'],transition_in=role['transition_in'],audio_continuity=role['audio_continuity'])
            result.append({'id':ident,'title':role['title']+(f' · part {part+1}' if count>1 else ''),'image_prompt':'','motion_prompt':'','narration':'','duration_seconds':math.ceil(retained),'edit_duration_seconds':retained,'edit_in_seconds':0,'image_asset':None,'video_asset':None,'direction':direction,'_source_role':role.get('source_role_id','')})
    for shot in result: shot['direction']['editorial']['audio_source_shot_id']=source_ids.get(shot.pop('_source_role'),'')
    if len(result)>200: raise StudioError('sequence_too_large','Reduce runtime: this pattern would exceed 200 planned clips.')
    return result


class Sequences:
    def preview_sequence(self, project_id, sequence_id):
        p=self.get(project_id); sequence=sequence_by_id(sequence_id); shots=plan(p,sequence); counts=has_work(p)
        return {'source_revision':p['revision'],'sequence_id':sequence_id,'roles':shots,'shot_count':len(shots),'replacement_required':any(counts.values()),'existing_work':counts}

    def apply_sequence(self, project_id, sequence_id, expected_revision, confirm_replace=False, actor='user'):
        if actor!='user': raise StudioError('human_only','Applying a sequence belongs to the user. Agents may propose and edit coverage through the normal planning tools.',403)
        if type(expected_revision) is not int: raise StudioError('invalid_revision','Refresh the project revision before applying a sequence.')
        if type(confirm_replace) is not bool: raise StudioError('invalid_input','confirm_replace must be true or false.')
        sequence=sequence_by_id(sequence_id)
        def update(p):
            shots=plan(p,sequence)
            if any(j['status']=='running' for j in p['jobs']): raise StudioError('job_running','Wait for running generation before replacing the shot plan.',409)
            if any(has_work(p).values()) and not confirm_replace: raise StudioError('sequence_replace_confirmation','This project contains authored work or media. Preview the replacement and explicitly confirm replacing the shot plan.',409)
            self._invalidate(p,'script')
            p['documents'].pop('script',None)
            p['shots']=shots
            p['production']['story']['sequence_id']=sequence_id
            p['production']['story']['beats']=[]
            p['production']['defaults']['action']['continuity_from']=''
            p['production']['defaults']['editorial']['audio_source_shot_id']=''
            p['steps']['brief']['ready']=bool(p['documents'].get('brief',{}).get('text'))
            self._progress(p)
            from .workflow import event
            event(p,'sequence_applied',actor,'Applied '+sequence['name']+' as a coverage plan; old media retained stale; editing stays external')
        return self.mutate(project_id,expected_revision,update)
