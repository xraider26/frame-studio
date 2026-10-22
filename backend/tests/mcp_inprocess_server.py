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
studio_mcp.mcp.run(transport='stdio')
