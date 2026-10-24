"""Explicit JSON job API connector; provider-specific APIs require an adapter."""
import asyncio
import base64
import json
import re
import uuid
import copy
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from .store import StudioError
from .workflow import event
from .comfy import validate_config, validate_installed, execute_comfy, ComfyError


def decode_output(data, kind):
    output = data.get('output', {})
    allowed = {'image': {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'},
               'video': {'video/mp4': '.mp4'}}
    suffix = allowed.get(kind, {}).get(output.get('mime_type'))
    value = output.get('base64')
    if data.get('status') != 'succeeded' or not suffix or not isinstance(value, str) or len(value) > 90_000_000:
        raise ValueError('Expected succeeded with output.base64 and the requested image/video mime_type. URL-only results require a provider adapter.')
    return base64.b64decode(value, validate=True), suffix


class Providers:
    def __init__(self, studio, config_path):
        self.studio, self.config_path = studio, Path(config_path)
        self.connections = json.loads(self.config_path.read_text()) if self.config_path.exists() else {}
        self.tasks = set()
        self.comfy_locks = {}

    def public(self):
        result = copy.deepcopy([{k: v for k, v in c.items() if k != 'api_key'} for c in self.connections.values()])
        for connection in result:
            if connection.get('adapter') == 'comfyui':
                # Browsers cannot round-trip uint64 seeds through JavaScript numbers.
                connection['comfy_json'] = json.dumps(connection['comfy'], indent=2, ensure_ascii=False)
        return result

    def save(self, data):
        key = data.get('id', '')
        url = data.get('base_url', '').rstrip('/')
        parsed = urlparse(url)
        if not re.fullmatch(r'[a-z0-9-]{1,50}', key) or parsed.scheme not in ['http', 'https'] or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise StudioError('invalid_connection', 'Use a simple connection ID and an HTTP(S) base URL without credentials or query parameters.')
        if parsed.scheme != 'https' and parsed.hostname not in ['127.0.0.1', 'localhost', '::1']:
            raise StudioError('invalid_connection', 'Remote generators require HTTPS. HTTP is allowed for local generators.')
        maximum = data.get('max_requests', 1)
        if type(maximum) is not int or not 1 <= maximum <= 1000:
            raise StudioError('invalid_connection', 'Set a request limit between 1 and 1000.')
        old = self.connections.get(key, {})
        adapter = data.get('adapter', old.get('adapter', 'json_job_api'))
        if adapter not in ['json_job_api', 'comfyui']:
            raise StudioError('invalid_connection', 'Choose json_job_api or comfyui.')
        extra = {'adapter': adapter}
        if adapter == 'comfyui':
            try:
                raw = data.get('comfy_json')
                if raw is not None and (not isinstance(raw,str) or len(raw)>2_000_000):
                    raise ValueError('ComfyUI configuration must be JSON text of at most 2 MB.')
                extra['comfy'] = validate_config(json.loads(raw) if raw is not None else data.get('comfy', old.get('comfy')))
            except ValueError as exc:
                raise StudioError('invalid_comfy_workflow', str(exc)) from exc
        self.connections[key] = {'id': key, 'name': str(data.get('name', key))[:100], 'base_url': url,
                                 'api_key': data.get('api_key') or old.get('api_key', ''), 'has_key': bool(data.get('api_key') or old.get('api_key')),
                                 'enabled': data.get('enabled') is True, 'max_requests': maximum, 'used_requests': old.get('used_requests', 0), **extra}
        self._save()
        return self.public()

    def _save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.connections, indent=2), encoding='utf-8')
        tmp.replace(self.config_path)

    def submit(self, job_id, connection_id):
        conn = self.connections.get(connection_id)
        if not conn or not conn['enabled']:
            raise StudioError('not_connected', 'Choose a configured and enabled API generator first.', 409)
        if conn['used_requests'] >= conn['max_requests']:
            raise StudioError('request_limit', 'This connection has reached its user-configured request limit.', 409)
        project, _ = self.studio.find_job(job_id)
        _, pending = self.studio.find_job(job_id)
        if conn.get('adapter') == 'comfyui' and pending['kind'] != conn['comfy']['kind']:
            raise StudioError('wrong_workflow_kind', 'Choose a ComfyUI connection for this media kind.', 409)
        def start(p):
            j = next(j for j in p['jobs'] if j['id'] == job_id)
            if j['status'] != 'awaiting_external_output':
                raise StudioError('job_closed', 'Job is already running or closed.', 409)
            block = self.studio._dispatch_block(p, j['kind'], existing_job=job_id)
            if block:
                raise StudioError('dispatch_blocked', block, 409)
            action = self.studio._next(p)
            if action.get('action') != 'generate' or any(action.get(k) != j.get(k) for k in ['step', 'shot_id', 'kind']):
                raise StudioError('step_blocked', 'This generation is blocked by the current workflow or approval policy. Read next_action first.', 409)
            j.update(status='running', executor=connection_id)
            event(p, 'provider_started', 'studio', 'Submitted to ' + conn['name'])
        self.studio.mutate(project['id'], None, start)
        conn['used_requests'] += 1
        self._save()
        task = asyncio.create_task(self._run(job_id, copy.deepcopy(conn)))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return {'job_id': job_id, 'status': 'running', 'connection_id': connection_id}

    async def _run(self, job_id, conn):
        try:
            _, job = self.studio.find_job(job_id)
            if conn.get('adapter') == 'comfyui':
                await self._run_comfy(job_id, conn)
                return
            headers = {'Authorization': 'Bearer ' + conn['api_key']} if conn['api_key'] else {}
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.post(conn['base_url'] + '/generate', json=job['handoff'], headers=headers)
                response.raise_for_status()
                data = response.json()
                for _ in range(60):
                    if data.get('status') == 'succeeded':
                        break
                    if data.get('status') not in ['queued', 'running'] or not data.get('job_id'):
                        raise ValueError('Generator returned an unsupported job response.')
                    await asyncio.sleep(2)
                    response = await client.get(conn['base_url'] + '/jobs/' + quote(str(data['job_id']), safe=''), headers=headers)
                    response.raise_for_status()
                    data = response.json()
                content, suffix = decode_output(data, job['kind'])
            path = self.studio.inbox / (uuid.uuid4().hex + suffix)
            path.write_bytes(content)
            try:
                self.studio.return_result(job_id, str(path), conn['name'])
            finally:
                path.unlink(missing_ok=True)
        except asyncio.CancelledError:
            self._failed(job_id, 'interrupted', 'Server stopped during execution; check provider before retrying.')
            raise
        except ComfyError as exc:
            self._failed(job_id, 'failed', str(exc))
        except Exception:
            # Do not echo provider HTTP bodies/URLs which can contain secrets.
            self._failed(job_id, 'failed', ('ComfyUI connection or media validation failed. Check availability, installed workflow and remote prompt history before retrying; no output was accepted.' if conn.get('adapter') == 'comfyui' else 'Generation failed: check API availability, credentials and JSON connector response format. No output was attached. A provider may still charge for a submitted request; inspect it before retrying.'))

    async def validate_connection(self, connection_id):
        conn = self.connections.get(connection_id)
        if not conn or conn.get('adapter') != 'comfyui':
            raise StudioError('invalid_connection', 'Choose a saved ComfyUI connection.')
        try:
            async with httpx.AsyncClient(base_url=conn['base_url'], headers=self._headers(conn), timeout=30, follow_redirects=False) as client:
                response = await client.get('/object_info'); response.raise_for_status()
                return validate_installed(conn['comfy'], response.json())
        except ComfyError as exc:
            raise StudioError('comfy_validation', str(exc)) from exc
        except Exception as exc:
            raise StudioError('comfy_unavailable', 'Cannot read ComfyUI node schemas. Check the server address, credentials and availability.', 409) from exc

    @staticmethod
    def _headers(conn):
        return {'Authorization': 'Bearer ' + conn['api_key']} if conn.get('api_key') else {}

    async def _run_comfy(self, job_id, conn):
        parsed = urlparse(conn['base_url'])
        host = parsed.hostname.lower()
        if host in ['localhost', '::1']: host = '127.0.0.1'
        lock_key = (host, parsed.port or (443 if parsed.scheme == 'https' else 80))
        lock = self.comfy_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            project, job = self.studio.find_job(job_id)
            def check_current():
                saved = self.connections.get(conn['id'], {})
                if not saved.get('enabled') or saved.get('adapter') != 'comfyui' or saved.get('base_url') != conn['base_url'] or saved.get('comfy') != conn['comfy']:
                    raise ComfyError('The ComfyUI connection was disabled or changed before submission. Review it before claiming a new generation.')
                current, pending = self.studio.find_job(job_id)
                shot = next((s for s in current['shots'] if s['id'] == pending['shot_id']), None)
                action = self.studio._next(current)
                block = self.studio._dispatch_block(current, pending['kind'], existing_job=job_id)
                if pending['actor'] != 'user': self.studio.require_workflow_contract(current['id'], pending['actor'])
                if pending['status'] != 'running' or block or not shot or self.studio._fingerprint(current, shot, pending['kind']) != pending['fingerprint'] or action.get('action') != 'generate' or any(action.get(k) != pending.get(k) for k in ['step','shot_id','kind']):
                    raise ComfyError('The project or its dispatch policy changed while waiting. Read current next_action before claiming a new generation.')
            check_current()
            def record(prompt_id):
                def update(p):
                    current = next(j for j in p['jobs'] if j['id'] == job_id)
                    current.update(remote_prompt_id=prompt_id, provider_adapter='comfyui')
                self.studio.mutate(project['id'], None, update)
            async with httpx.AsyncClient(base_url=conn['base_url'], headers=self._headers(conn), timeout=60, follow_redirects=False) as client:
                path = await execute_comfy(client, conn['comfy'], job['handoff'], self.studio.media_root, self.studio.inbox, record, before_submit=check_current)
            try:
                self.studio.return_result(job_id, str(path), conn['name'])
            finally:
                path.unlink(missing_ok=True)

    def _failed(self, job_id, status, message):
        try:
            project, _ = self.studio.find_job(job_id)
        except StudioError:
            return
        def fail(p):
            job = next(j for j in p['jobs'] if j['id'] == job_id)
            if job['status'] != 'running':
                return
            job.update(status=status, error=message)
            event(p, 'provider_' + status, 'studio', message)
        self.studio.mutate(project['id'], None, fail)

    def reconcile(self):
        for p in self.studio.all():
            for j in p['jobs']:
                if j['status'] == 'running':
                    self._failed(j['id'], 'interrupted', 'Server restarted. Confirm provider outcome before submitting a new job.')
