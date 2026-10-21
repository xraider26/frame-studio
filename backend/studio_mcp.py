"""Local stdio MCP bridge. The persistent studio backend owns all state/jobs."""
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('STUDIO_DATA_DIR', ROOT / 'studio_data'))
API = os.environ.get('STUDIO_API_URL', 'http://127.0.0.1:8010').rstrip('/')
ACTOR = os.environ.get('STUDIO_CLIENT_NAME', 'mcp-agent')
mcp = FastMCP('Frame Studio', instructions='Read studio_capabilities and get_project. Follow next_action; never invent outputs. Complete text steps with complete_step. For generation, claim_generation, use your authorized local/API tool, save its real output in the returned inbox, then return_generation. Approval policy is user controlled. await_approval means stop and let the user review. Refresh after mutations and before using expected_revision. API connections are optional, separately configured executors.')


async def command(operation, arguments=None):
    token = os.environ.get('STUDIO_AGENT_TOKEN')
    if not token:
        file = DATA / 'agent.token'
        if not file.exists():
            raise ValueError('backend_unavailable: Start launch-studio.ps1 first; no studio token exists.')
        token = file.read_text(encoding='utf-8').strip()
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(API + '/studio/v1/command', headers={'Authorization': 'Bearer ' + token}, json={'operation': operation, 'arguments': arguments or {}, 'actor': ACTOR})
        result = response.json()
        if response.is_error:
            raise ValueError(f"{result.get('error', 'studio_error')}: {result.get('message', result.get('detail', 'Request failed'))}")
        return result
    except httpx.RequestError as exc:
        raise ValueError('backend_unavailable: Studio API is not reachable. Start launch-studio.ps1 and retry.') from exc


@mcp.tool()
async def studio_capabilities() -> dict:
    """Read workflow steps, templates, connected API generators and the local output inbox."""
    return await command('studio_capabilities')


@mcp.tool()
async def list_projects() -> list[dict]:
    """List saved studio projects shared with the browser UI."""
    return await command('list_projects')


@mcp.tool()
async def create_project(name: str, template_id: str = 'custom', request_id: str = '') -> dict:
    """Create a project. Use a stable unique request_id to avoid duplicate projects on retries."""
    return await command('create_project', locals())


@mcp.tool()
async def duplicate_project(project_id: str, name: str) -> dict:
    """Create an independent copy of the plan, settings and references. Jobs, generated takes and approvals start fresh with review enabled. Original project is unchanged."""
    return await command('duplicate_project', locals())


@mcp.tool()
async def export_generation_package(project_id: str) -> dict:
    """Build a real portable ZIP for a Flow agent or other generator without API access: manifest.json, generator-specific prompts.md and local reference images. Not native Flow/Runway project format. Share the file with the user's chosen agent; it must check the current review policy before executing."""
    result = await command('export_handoff', locals())
    return {'path': result['path'], 'download_url': result['download_url'], 'source_revision': result['manifest']['source_revision'],
            'video_generator': result['manifest']['video_generator'], 'files': ['manifest.json', 'prompts.md', 'README.txt', 'references/ (when available)']}


@mcp.tool()
async def get_project(project_id: str) -> dict:
    """Read project revision, next_action, shots, review policies, assets, jobs and activity."""
    return await command('get_project', locals())


@mcp.tool()
async def next_action(project_id: str) -> dict:
    """Find the next permitted workflow step. Stop when it says await_approval."""
    return await command('next_action', locals())


@mcp.tool()
async def update_settings(project_id: str, settings: dict[str, Any], expected_revision: int) -> dict:
    """Apply creative controls. Changed settings reopen dependent outputs and review steps."""
    return await command('update_settings', locals())


@mcp.tool()
async def update_shots(project_id: str, shots: list[dict[str, Any]], expected_revision: int) -> dict:
    """Save the complete ordered shot list (1–200). Include existing IDs when editing. Fields: title, image_prompt, motion_prompt, narration, duration_seconds. This replaces the current plan and invalidates its generated outputs while preserving takes."""
    return await command('update_shots', locals())


@mcp.tool()
async def complete_step(project_id: str, step: str, output: dict[str, Any], expected_revision: int) -> dict:
    """Return a real brief, script or editor_handoff document as {text: ...}. Media stages complete only through returned files; final_review requires an imported final MP4. Human-required steps wait in the studio."""
    return await command('complete_step', locals())


@mcp.tool()
async def claim_generation(project_id: str, request_id: str) -> dict:
    """Get a durable generation handoff for the next shot. It contains job_id, prompts, creative settings, reference file paths, output requirements and return inbox. already_claimed means an executor already owns it; inspect rather than starting duplicate paid work."""
    return await command('claim_generation', locals())


@mcp.tool()
async def return_generation(job_id: str, output_path: str) -> dict:
    """Attach the actual generated image/MP4 from the studio inbox to this exact job, then get the next action. Duplicate returns are idempotent. Old revisions are retained as stale and do not advance the current workflow."""
    return await command('return_generation', locals())


@mcp.tool()
async def get_job(job_id: str) -> dict:
    """Inspect the saved generation task, immutable handoff, output asset or provider error."""
    return await command('get_job', locals())


@mcp.tool()
async def cancel_job(job_id: str) -> dict:
    """Cancel an external handoff not yet returned. Does not cancel a running third-party paid call."""
    return await command('cancel_job', locals())


@mcp.tool()
async def import_reference(project_id: str, path: str, name: str, expected_revision: int) -> dict:
    """Import a real image reference from the allowed inbox. Changing references invalidates dependent work."""
    return await command('import_reference', locals())


@mcp.tool()
async def import_final(project_id: str, path: str, expected_revision: int) -> dict:
    """Return the actual final MP4 made in external editing software for final review."""
    return await command('import_final', locals())


@mcp.tool()
async def editor_handoff(project_id: str) -> dict:
    """Get ordered take paths, narration, timing and editing notes for an external editor."""
    return await command('editor_handoff', locals())


@mcp.tool()
async def run_provider(job_id: str, connection_id: str) -> dict:
    """Execute a claimed handoff using a user-configured, enabled JSON Job API generator, subject to its request limit. This can incur provider costs. Do not run if the user requested agent/local generation instead. Poll get_job; no auto retry of paid calls."""
    return await command('run_provider', locals())


if __name__ == '__main__':
    mcp.run(transport='stdio')
