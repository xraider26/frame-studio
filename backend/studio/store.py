import json
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path
from .templates import DEFAULT_SETTINGS
from .creative import default_production, Direction, merge


def load(value):
    project = json.loads(value)
    project['settings'] = dict(DEFAULT_SETTINGS, **project['settings'])
    project['schema_version'] = 2
    project.setdefault('dispatch', {'paused': False, 'priority': 0, 'blocked_reason': ''})
    defaults = default_production(project.get('template_id', 'custom'))
    if 'production' not in project:
        defaults['defaults'] = Direction().model_dump()
    project['production'] = merge(defaults, project.get('production', {}))
    for shot in project['shots']:
        shot['direction'] = merge(Direction().model_dump(), shot.get('direction', {}))
        shot.setdefault('edit_duration_seconds', shot['duration_seconds'])
        shot.setdefault('edit_in_seconds', 0)
    return project


class StudioError(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


class Store:
    def __init__(self, path):
        self.db_path = Path(path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.db_path.with_name(self.db_path.stem + '.pre-creative-v2.sqlite3')
        if self.db_path.exists() and not backup.exists():
            with closing(sqlite3.connect(self.db_path)) as source:
                table = source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='studio_projects'").fetchone()
                if table and any(json.loads(row[0]).get('schema_version', 1) < 2 for row in source.execute('SELECT payload FROM studio_projects')):
                    with closing(sqlite3.connect(backup)) as target:
                        source.backup(target)
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS studio_projects (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS studio_templates (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS studio_batches (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS studio_tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL, status TEXT NOT NULL, expires_at TEXT NOT NULL, payload TEXT NOT NULL)')
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS studio_active_task ON studio_tasks(project_id) WHERE status='active'")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            with conn:
                yield conn
        finally:
            conn.close()

    def all(self):
        with self.connect() as conn:
            return [load(row[0]) for row in conn.execute('SELECT payload FROM studio_projects ORDER BY rowid DESC')]

    def get(self, project_id):
        with self.connect() as conn:
            row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (project_id,)).fetchone()
            if not row:
                raise StudioError('not_found', 'Project not found', 404)
            project = load(row[0])
            if project.get('deleted_at'):
                raise StudioError('project_deleted', 'Project is in Trash. Restore it in the studio first.', 409)
            return project

    def insert(self, project):
        with self.connect() as conn:
            conn.execute('INSERT INTO studio_projects VALUES (?,?)', (project['id'], json.dumps(project)))
        return project

    def mutate(self, project_id, expected_revision, fn, allow_deleted=False):
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT payload FROM studio_projects WHERE id=?', (project_id,)).fetchone()
            if not row:
                raise StudioError('not_found', 'Project not found', 404)
            project = load(row[0])
            if project.get('deleted_at') and not allow_deleted:
                raise StudioError('project_deleted', 'Project is in Trash. Restore it in the studio first.', 409)
            if expected_revision is not None and project['revision'] != expected_revision:
                raise StudioError('revision_conflict', f"Project changed. Refresh revision {project['revision']} before retrying.", 409)
            result = fn(project)
            project['revision'] += 1
            project['history'] = project['history'][-500:]
            conn.execute('UPDATE studio_projects SET payload=? WHERE id=?', (json.dumps(project), project_id))
        return project if result is None else result
