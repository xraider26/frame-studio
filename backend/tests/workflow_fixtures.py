"""Explicit creator answers for tests exercising later workflow stages."""
CREATOR_SETTINGS = {'image_model': 'Fixture image model', 'video_model': 'Fixture video model',
    'creative_intake': {'vision': 'A traveler discovers an observatory', 'art_style': 'Cinematic realism', 'purpose': 'A short film'}}


def creator_ready(studio, project):
    return studio.update_settings(project['id'], CREATOR_SETTINGS, project['revision'], 'user')


def record_fixture_execution(studio, job_id):
    """Explicit synthetic-generator request evidence for actual fixture media returns."""
    project, job = studio.find_job(job_id)
    if not job.get('execution'):
        handoff = job['handoff']
        studio.record_generation_execution(job_id, {'tool': 'synthetic-fixture-generator',
            'prompt': handoff['prompt'], 'negative_prompt': handoff.get('negative_prompt', ''),
            'references': handoff.get('references', []), 'arguments': {'fixture_only': True}}, project['revision'], job['actor'])


def return_fixture(studio, job_id, output_path, actor):
    record_fixture_execution(studio, job_id)
    return studio.return_result(job_id, output_path, actor)
