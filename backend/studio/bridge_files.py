"""Authenticated byte transport between a local MCP client and desktop service."""
from contextlib import asynccontextmanager
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import quote
import uuid
import json
import httpx

LIMIT = 500*1024*1024


@asynccontextmanager
async def connection(data, api):
    token = os.environ.get('STUDIO_AGENT_TOKEN')
    if not token:
        try:
            token = (data/'agent.token').read_text(encoding='utf-8').strip()
        except OSError as exc:
            raise ValueError('backend_unavailable: Open Orchestra and reconnect MCP.') from exc
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        instance = os.environ.get('STUDIO_DESKTOP_INSTANCE')
        if instance:
            response = await client.get(api+'/health')
            response.raise_for_status()
            health = response.json()
            if health.get('service') != 'frame-studio' or health.get('status') != 'ok' or health.get('instance_id') != instance:
                raise ValueError('backend_unavailable: The desktop instance changed; reconnect MCP.')
        yield client, {'Authorization':'Bearer '+token}


def result(response):
    payload = response.json()
    if response.is_error:
        raise ValueError(f"{payload.get('error', 'studio_error')}: {payload.get('message', payload.get('detail', 'Request failed'))}")
    return payload


async def upload_output(data, api, actor, job_id, output_path):
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise ValueError('invalid_job: Use the actual claimed job ID.')
    source = Path(output_path)
    if not source.is_file() or source.stat().st_size > LIMIT or source.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.mp4'}:
        raise ValueError('invalid_asset: Provide an actual PNG/JPEG/WebP/MP4 file up to 500 MB.')
    async with connection(data, api) as (client, headers):
        with source.open('rb') as stream:
            response = await client.post(api+'/studio/v1/jobs/'+job_id+'/output', headers=headers,
                                         data={'actor':actor}, files={'file':(source.name, stream, 'application/octet-stream')})
        return result(response)


async def stage_references(data, api, handoff):
    refs = handoff.get('references', [])
    if not refs:
        return []
    cache = Path.home()/'.orchestra'/'reference-cache'
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    staged = []
    async with connection(data, api) as (client, headers):
        for ref in refs:
            if not re.fullmatch(r'[a-f0-9]{32}', ref['id']):
                raise ValueError('invalid_reference: Expected a registered media ID.')
            name = Path(ref['path']).name
            suffix = Path(name).suffix.lower()
            if suffix not in {'.png','.jpg','.jpeg','.webp','.mp4'}:
                raise ValueError('invalid_reference: Unsupported media reference.')
            destination = cache/(ref['id']+'-v'+str(ref['version'])+suffix)
            temporary = cache/('download-'+uuid.uuid4().hex+suffix)
            try:
                url = api+'/studio/v1/media/'+quote(handoff['project_id'], safe='')+'/'+quote(name, safe='')
                async with client.stream('GET', url, headers=headers) as response:
                    response.raise_for_status()
                    size = 0
                    with temporary.open('xb') as stream:
                        async for chunk in response.aiter_bytes(1024*1024):
                            size += len(chunk)
                            if size > LIMIT:
                                raise ValueError('invalid_reference: Media exceeds 500 MB.')
                            stream.write(chunk)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            with destination.open('rb') as stream:
                checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
            staged.append({'id':ref['id'], 'version':ref['version'], 'slot':ref['slot'], 'path':str(destination), 'sha256':checksum})
    return staged


def observed_reference_files(execution):
    paths = execution.get('arguments', {}).get('referenced_image_paths')
    if paths is None:
        return None
    if not isinstance(paths, list) or len(paths) > 100:
        raise ValueError('invalid_reference: Use the actual submitted reference paths.')
    observed = []
    for path in paths:
        file = Path(path)
        if not file.is_file() or file.stat().st_size > LIMIT:
            raise ValueError('invalid_reference: A submitted local reference is missing or too large.')
        with file.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        observed.append({'path':path, 'sha256':checksum})
    return observed


async def upload_reference(data, api, actor, source_path, fields, *, decision=None):
    source = Path(source_path)
    if not source.is_file() or source.stat().st_size > LIMIT or source.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.mp4'}:
        raise ValueError('invalid_reference: Provide an actual image/MP4 up to 500 MB.')
    if decision is not None:
        form = {'actor':actor, 'decision':json.dumps(decision)}
        endpoint = '/studio/v1/creator-reference'
    else:
        form = {'actor':actor, 'role':'reference', **{k:str(v) for k,v in fields.items() if v is not None}}
        endpoint = '/studio/v1/upload'
    async with connection(data, api) as (client, headers):
        with source.open('rb') as stream:
            response = await client.post(api+endpoint, headers=headers, data=form, files={'file':(source.name,stream,'application/octet-stream')})
        return result(response)
