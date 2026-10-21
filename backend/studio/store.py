import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .templates import DEFAULT_SETTINGS


def load(value):
    project = json.loads(value)
    project['settings'] = dict(DEFAULT_SETTINGS, **project['settings'])
    return project


class StudioError(ValueError):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


class Store:
    def __init__(self, path):
        self.db_path = Path(path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS studio_projects (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

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
