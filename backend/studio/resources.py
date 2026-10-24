"""Conservative resource ledger. External reservations stay until cost is reported."""
from decimal import Decimal


def exposure(job):
    cost = job.get('cost', {})
    return cost.get('actual') if cost.get('actual') is not None else cost.get('planned')


def total(jobs):
    return float(sum((Decimal(str(exposure(j))) for j in jobs if exposure(j) is not None), Decimal(0)))


def imported_costs(project):
    return [a for a in project['assets'] if a.get('provenance', {}).get('type') == 'externally_created']


def cost_entries(project):
    return project['jobs'] + imported_costs(project)


def resource_gate(project, shot, kind, step, fingerprint):
    r = project['production']['resources']
    jobs = project['jobs']
    active = next((j for j in jobs if j['fingerprint'] == fingerprint and j['status'] in ['awaiting_external_output', 'queued', 'running']), None)
    price = r[kind + '_cost']
    bounded = r['limit'] is not None or (step == 'pilot' and r['pilot_limit'] is not None)
    if bounded and (any(exposure(j) is None for j in cost_entries(project)) or (not active and (price is None or not r['cost_evidence']))):
        return 'A hard budget needs evidenced planned costs and known/reserved amounts for previous jobs. Record missing costs first.'
    additional = 0 if active else (price or 0)
    if r['limit'] is not None and Decimal(str(total(cost_entries(project)))) + Decimal(str(additional)) > Decimal(str(r['limit'])):
        return 'Total budget is exhausted or would be exceeded by this handoff.'
    pilot_jobs = [j for j in jobs if j['step'] == 'pilot']
    if step == 'pilot' and r['pilot_limit'] is not None and Decimal(str(total(pilot_jobs))) + Decimal(str(additional)) > Decimal(str(r['pilot_limit'])):
        return 'Pilot budget would be exceeded. Review the pilot resource limit.'
    attempts = sum(j['shot_id'] == shot['id'] and j['kind'] == kind for j in jobs)
    if not active and r['max_attempts_per_shot'] is not None and attempts >= r['max_attempts_per_shot']:
        return 'Attempt limit reached for this shot and media kind. Review the defect and redesign before raising the limit.'
    return None


def metrics(project):
    known = total(cost_entries(project))
    selected = sum(bool(s['image_asset'] if project.get('output_type') == 'image' else s['video_asset']) for s in project['shots'])
    unknown = sum(exposure(j) is None for j in cost_entries(project))
    durations = []
    from datetime import datetime
    for job in project['jobs']:
        if job.get('completed_at'):
            durations.append(max(0, (datetime.fromisoformat(job['completed_at']) - datetime.fromisoformat(job['created_at'])).total_seconds()))
    return {'unit': project['production']['resources']['unit'], 'attempts': len(project['jobs']),
            'reserved_or_spent': known, 'unknown_cost_imports': sum(exposure(a) is None for a in imported_costs(project)), 'unknown_cost_jobs': unknown, 'selected_video_shots': selected,
            'cost_per_selected_shot': round(known / selected, 4) if selected and not unknown else None,
            'completed_job_seconds': round(sum(durations), 1),
            'reported_defects': sum(bool(a.get('review', {}).get('defect')) for a in project['assets'])}
