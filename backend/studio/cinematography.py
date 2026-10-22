"""Source-linked teaching visuals, separate from provider output evidence."""
import json
from pathlib import Path, PurePosixPath

from .course_rules import source_rules


PUBLIC_ROOT = Path(__file__).resolve().parents[2] / 'frontend' / 'public'

CATEGORY_RULES = {
    'camera': ['appearance'], 'lens': ['appearance', 'framing'],
    'framing': ['framing'], 'lighting': ['light'], 'movement': ['motion'],
}


def generated_samples():
    """Only advertise existing assets with complete, versioned generation metadata."""
    asset_root = (PUBLIC_ROOT / 'cinematography').resolve()
    try:
        manifest = json.loads((asset_root / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        return {}
    if manifest.get('tool') != 'built-in image_gen' or not isinstance(manifest.get('examples'), list):
        return {}
    samples = {}
    for example in manifest['examples']:
        if not isinstance(example, dict):
            continue
        fields = ['id', 'image', 'prompt', 'caption', 'comparison_group', 'tool']
        if any(not isinstance(example.get(key), str) or not example[key].strip() for key in fields):
            continue
        if example['tool'] != 'built-in image_gen':
            continue
        image = example['image']
        if any(char in image for char in ['\\', '%', '?', '#', ':']):
            continue
        relative = image.removeprefix('/')
        parts = PurePosixPath(relative).parts
        if not parts or parts[0] != 'cinematography' or '..' in parts:
            continue
        path = (PUBLIC_ROOT / relative).resolve()
        if not path.is_relative_to(asset_root) or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            continue
        if not path.is_file():
            continue
        samples[example['id']] = {key: example[key] for key in fields if key != 'id'}
        samples[example['id']].update(image='/' + relative, kind='generated_still')
    return samples


def enrich_visual_entries(entries):
    rules = {rule['id']: rule for rule in source_rules()}
    samples = generated_samples()
    sample_count = 0
    for entry in entries:
        rule_ids = CATEGORY_RULES.get(entry['category'], [])
        if not rule_ids:
            continue
        citations = {}
        for rule_id in rule_ids:
            for citation in rules[rule_id]['citations']:
                citations[(citation['source_id'], citation['page'])] = citation
        entry['citations'] = list(citations.values())
        entry['source_rule_ids'] = rule_ids.copy()
        entry['citation_scope'] = 'Selected original pages support linked teaching principles; this visual example and its application are studio-authored adaptations, not literal course catalogue entries.'
        if entry['category'] == 'movement':
            entry['visual']['motion'] = {'id': entry['id'], 'duration_seconds': 6,
                                         'kind': 'spatial_demonstration'}
        elif entry['id'] in samples:
            entry['visual']['sample'] = samples[entry['id']]
            sample_count += 1
    return entries, sample_count
