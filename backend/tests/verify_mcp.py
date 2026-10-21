"""Live stdio roundtrip against an explicitly isolated test backend."""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import httpx
from PIL import Image
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '.studio-test' / 'data'
URL = 'http://127.0.0.1:8011'


async def main():
    environment = dict(os.environ, STUDIO_DATA_DIR=str(DATA), STUDIO_API_URL=URL, STUDIO_CLIENT_NAME='mcp-verification')
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'backend' / 'studio_mcp.py')], env=environment)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert {'claim_generation', 'return_generation', 'complete_step', 'get_project', 'duplicate_project', 'export_generation_package'} <= names
            assert 'review' not in names and 'set_policy' not in names

            async def call(name, args=None):
                result = await client.call_tool(name, args or {})
                assert not result.isError, result.content
                return json.loads(next(x.text for x in result.content if x.type == 'text'))

            p = await call('create_project', {'name': 'MCP roundtrip · verification fixture', 'template_id': 'short-drama', 'request_id': 'verification-project-' + uuid.uuid4().hex})
            async with httpx.AsyncClient() as http:
                r = await http.post(URL + '/studio/v1/command', headers={'Authorization': 'Bearer ' + (DATA / 'browser.token').read_text().strip()}, json={'operation': 'set_policy', 'arguments': {'project_id': p['id'], 'policy': {'brief': False, 'script': False}, 'expected_revision': p['revision']}})
                assert r.status_code == 200, r.text
                p = r.json()
            for step, text in [('brief', 'A traveler discovers a silent observatory. Audience: cinematic short-drama viewers.'), ('script', 'Exterior. The traveler approaches. A warm light moves behind the abandoned dome.')]:
                p = await call('complete_step', {'project_id': p['id'], 'step': step, 'output': {'text': text}, 'expected_revision': p['revision']})
            p = await call('update_shots', {'project_id': p['id'], 'expected_revision': p['revision'], 'shots': [{'title': 'The observatory', 'image_prompt': 'Traveler outside an observatory at dusk. Character wardrobe: rust-colored coat. Wide cinematic frame.', 'motion_prompt': 'Slow dolly toward the observatory as the traveler takes one step.', 'duration_seconds': 6}]})
            task = await call('claim_generation', {'project_id': p['id'], 'request_id': 'verification-image'})
            assert task['handoff']['kind'] == 'image'
            file = DATA / 'inbox' / 'verification-fixture.png'
            # Explicitly a synthetic fixture, not an AI generation.
            Image.new('RGB', (320, 180), '#b76735').save(file)
            returned = await call('return_generation', {'job_id': task['job']['id'], 'output_path': str(file)})
            assert returned['next_action']['action'] == 'await_approval'
            repeated = await call('return_generation', {'job_id': task['job']['id'], 'output_path': str(file)})
            assert returned['asset']['id'] == repeated['asset']['id']
            latest = await call('get_project', {'project_id': p['id']})
            assert latest['steps']['brief']['status'] == 'auto_proceeded'
            assert len(latest['assets']) == 1
            exported = await call('export_generation_package', {'project_id': p['id']})
            assert Path(exported['path']).is_file()
            duplicate = await call('duplicate_project', {'project_id': p['id'], 'name': 'MCP duplicate verification'})
            assert duplicate['id'] != p['id'] and duplicate['jobs'] == []
            # A second independently launched client reads the same saved records.
            async with stdio_client(params) as (read2, write2):
                async with ClientSession(read2, write2) as second:
                    await second.initialize()
                    result = await second.call_tool('get_project', {'project_id': p['id']})
                    snapshot = json.loads(next(x.text for x in result.content if x.type == 'text'))
                    assert snapshot['revision'] == latest['revision']
                    assert snapshot['assets'][0]['id'] == returned['asset']['id']
            (ROOT / '.studio-test' / 'verification.json').write_text(json.dumps({'project_id': p['id'], 'job_id': task['job']['id'], 'asset_id': returned['asset']['id']}))
            print('PASS: real MCP stdio handshake, tool discovery, agent project/shot creation, prompt handoff, real fixture return, manual review pause, automatic brief/script progression, idempotent return, generator ZIP export, duplication, and second-client persistence.')


if __name__ == '__main__':
    asyncio.run(main())
