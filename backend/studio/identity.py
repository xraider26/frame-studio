"""Versioned canonical identity, backed by actual copied reference images."""
import copy
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from .assets import checked_file
from .store import StudioError, load
from .batching import utc


class Identity:
    def _preserve_identity(self, p):
        locked = p.get('shared_identity', {}).get('entities', [])
        ids = {e['id'] for e in locked}
        if ids:
            p['production']['bible'] = [e for e in p['production']['bible'] if e['id'] not in ids] + copy.deepcopy(locked)

    def _guard_identity(self, p, production):
        lock = p.get('shared_identity', {})
        entities = {e['id']: e for e in production['bible']}
        for entity in lock.get('entities', []):
            if entities.get(entity['id']) != entity:
                raise StudioError('identity_locked', 'A canonical identity cannot be changed here. Edit the identity source project and sync the batch in Production queue.', 409)
        if p.get('batch_id') and self.get_batch(p['batch_id'])['auto_retry'] and not production['require_recorded_checks']:
            raise StudioError('quality_policy_required', 'Turn off batch automatic quality retries before disabling recorded quality checks.', 409)

    def _seed_identity(self, p, source, version, batch_id, copied):
        entities = copy.deepcopy(source['production']['bible'])
        if not entities:
            raise StudioError('identity_missing', 'Define the canonical characters, products or style in the source project bible first.')
        source_assets = {a['id']: a for a in source['assets']}
        mappings, references = {}, []
        for entity in entities:
            linked = []
            for n, asset_id in enumerate(entity['asset_ids']):
                if asset_id not in mappings:
                    asset = source_assets.get(asset_id)
                    if not asset or asset['kind'] != 'image' or (asset.get('stale') and (not asset.get('role') or asset.get('source_video'))):
                        raise StudioError('identity_reference_missing', 'Canonical bible assets must resolve to actual current image references.')
                    file, metadata = checked_file(asset['path'], [self.media_root], 'image')
                    new_id = uuid.uuid4().hex
                    dest = self.media_root / p['id'] / (new_id + metadata['suffix'])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, dest)
                    copied.append(dest)
                    mappings[asset_id] = new_id
                    p['assets'].append({'id': new_id, 'kind': 'image', 'role': 'reference', 'name': 'Canonical · ' + entity['name'],
                        'path': str(dest), 'url': f'/api/studio/media/{p["id"]}/{dest.name}', 'stale': False, 'version': 1,
                        'canonical_batch': batch_id, 'canonical_version': version, **metadata})
                new_id = mappings[asset_id]
                linked.append(new_id)
                references.append({'slot': 'canonical_' + hashlib.sha256(entity['id'].encode()).hexdigest()[:12] + '_' + str(n + 1),
                    'asset_id': new_id, 'version': 1, 'role': entity['kind'], 'entity_id': entity['id'],
                    'notes': f'Canonical identity version {version}: preserve {entity["name"]}; inspect actual generated output.'})
            entity['asset_ids'] = linked
        old_ids = {e['id'] for e in p.get('shared_identity', {}).get('entities', [])}
        incoming = {e['id'] for e in entities}
        p['production']['bible'] = [e for e in p['production']['bible'] if e['id'] not in old_ids | incoming] + entities
        # Remove IDs which no longer belong to the canonical cast from explicit shot/default links.
        removed = old_ids - incoming
        for d in [p['production']['defaults']] + [s['direction'] for s in p['shots']]:
            d['action']['visible_entities'] = [key for key in d['action']['visible_entities'] if key not in removed]
            if d['sound']['speaker_id'] in removed:
                d['sound']['speaker_id'] = ''
            d['references'] = [r for r in d['references'] if r['entity_id'] not in removed]
        p['shared_identity'] = {'batch_id': batch_id, 'version': version, 'source_project_id': source['id'],
                                'source_revision': source['revision'], 'entities': entities, 'references': references}

    def sync_batch_identity(self, batch_id, source_project_id, expected_revision, source_revision):
        copied = []
        try:
            with self.connect() as conn:
                if not conn.in_transaction:
                    conn.execute('BEGIN IMMEDIATE')
                batch = self.get_batch(batch_id)
                source = self.get(source_project_id)
                if batch['revision'] != expected_revision or source['revision'] != source_revision:
                    raise StudioError('revision_conflict', 'Batch or identity source changed. Refresh before synchronization.', 409)
                members = [load(r[0]) for r in conn.execute('SELECT payload FROM studio_projects')]
                members = [p for p in members if p.get('batch_id') == batch_id and not p.get('deleted_at')]
                if any(j['status'] == 'running' for p in members for j in p['jobs']):
                    raise StudioError('job_running', 'Wait for active API jobs before synchronizing canonical identity.', 409)
                version = batch['identity_version'] + 1
                for p in members:
                    before = copy.deepcopy(p)
                    self._seed_identity(p, source, version, batch_id, copied)
                    affected = self._changed_inputs(before, p)
                    if affected:
                        self._invalidate_selected(p, affected)
                    p['revision'] += 1
                    from .creator_chat import current_decision, append_decision
                    decision = current_decision()
                    p['history'].append({'at': utc(), 'type': 'identity_sync', 'actor': decision['actor'] if decision else 'user', 'message': f'Canonical identity synchronized to version {version}'})
                    self._progress(p)
                    if decision:
                        append_decision(p, decision)
                    conn.execute('UPDATE studio_projects SET payload=? WHERE id=?', (json.dumps(p), p['id']))
                batch.update(identity_version=version, identity_source_project_id=source_project_id, identity_source_revision=source_revision, revision=batch['revision'] + 1)
                conn.execute('UPDATE studio_batches SET payload=? WHERE id=?', (json.dumps(batch), batch_id))
            return batch
        except Exception:
            for file in copied:
                file.unlink(missing_ok=True)
            raise
