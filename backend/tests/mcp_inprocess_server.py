"""Test-only MCP stdio transport backed by the actual API through TestClient.

No listening server, browser, paid tool or live user database is used.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from studio.api import create_app
import studio_mcp

client = TestClient(create_app(os.environ['STUDIO_TEST_DATA'], 'test-agent', 'test-browser'))


async def inprocess_command(operation, arguments=None):
    response = client.post('/studio/v1/command', headers={'Authorization': 'Bearer test-agent'},
                           json={'operation': operation, 'arguments': arguments or {}, 'actor': 'sdk-test'})
    if response.is_error:
        raise ValueError(response.json()['message'])
    return response.json()


studio_mcp.command = inprocess_command
studio_mcp.ACTOR = 'sdk-test'


async def inprocess_upload_output(data, api, actor, job_id, output_path):
    # Exercise the actual byte-upload API while retaining this harness's
    # no-listening-port TestClient boundary.
    with Path(output_path).open('rb') as stream:
        response = client.post('/studio/v1/jobs/'+job_id+'/output', headers={'Authorization':'Bearer test-agent'},
                               data={'actor':actor}, files={'file':(Path(output_path).name,stream,'application/octet-stream')})
    if response.is_error:
        raise ValueError(str(response.json()))
    return response.json()


studio_mcp.upload_output = inprocess_upload_output
studio_mcp.mcp.run(transport='stdio')
