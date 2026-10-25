"""Per-user desktop discovery outside Windows' virtualized AppData directories.

Only a fresh agent-only bridge credential is published; project state and the
existing browser/agent credentials never move. Records are local secrets.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid


def connection_file(root):
    identity = os.path.normcase(os.path.abspath(root))
    key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    return Path.home() / '.orchestra' / 'desktop-connections' / (key + '.json')


def publish_connection(runtime, agent_token):
    file = connection_file(runtime['data_root'])
    file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = file.with_name(file.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'runtime': runtime, 'agent_token': agent_token}, stream)
        os.replace(temporary, file)
    finally:
        temporary.unlink(missing_ok=True)


def read_connection(root):
    file = connection_file(root)
    try:
        if file.stat().st_size > 16384:
            raise ValueError('Oversized desktop connection record')
        record = json.loads(file.read_text(encoding='utf-8'))
        if (not isinstance(record, dict) or not isinstance(record.get('runtime'), dict)
                or not isinstance(record.get('agent_token'), str) or not record['agent_token']):
            raise ValueError('Invalid desktop connection record')
        return record
    except FileNotFoundError:
        return None


def remove_connection(root, instance_id):
    record = read_connection(root)
    if record and record['runtime'].get('instance_id') == instance_id:
        connection_file(root).unlink(missing_ok=True)
