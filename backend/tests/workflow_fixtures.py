"""Explicit creator answers for tests exercising later workflow stages."""
CREATOR_SETTINGS = {'image_model': 'Fixture image model', 'video_model': 'Fixture video model',
    'creative_intake': {'vision': 'A traveler discovers an observatory', 'art_style': 'Cinematic realism', 'purpose': 'A short film'}}


def creator_ready(studio, project):
    return studio.update_settings(project['id'], CREATOR_SETTINGS, project['revision'], 'user')
