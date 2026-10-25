"""Build-machine verification of the actual installed service's stdio protocol."""
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from verify_chat_transport import verify_chat_transport


async def verify():
    service, data = sys.argv[1:3]
    clean = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'COMSPEC'}}
    clean['PATH'] = str(Path(os.environ['SYSTEMROOT']) / 'System32')
    clean['STUDIO_CLIENT_NAME'] = 'codex'
    params = StdioServerParameters(command=service, args=['mcp', '--data-dir', data], env=clean)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            names = {t.name for t in (await client.list_tools()).tools}
            assert {'recipe_catalog', 'knowledge_catalog', 'create_project', 'list_projects', 'start_project_setup', 'record_generation_execution', 'get_context', 'creator_decision'} <= names
            assert not {'review', 'set_policy'} & names
            capabilities = await client.call_tool('studio_capabilities', {})
            assert not capabilities.isError, capabilities.content
            result = await client.call_tool('recipe_catalog', {})
            assert not result.isError, result.content
            content = result.structuredContent
            if content is None:
                content = json.loads(next(c.text for c in result.content if c.type == 'text'))
            content = content.get('result', content)
            assert len(content['recipes']) == 16
            assert sum(r.get('output_type') == 'image' for r in content['recipes']) == 7
            print(json.dumps(await verify_chat_transport(client)), flush=True)
            print(json.dumps({'stdio': 'passed', 'tools': len(names), 'recipes': len(content['recipes'])}))


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(verify(), 60))
