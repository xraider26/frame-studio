import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .providers import Providers
from .store import StudioError
from .templates import LABELS, STEPS, TEMPLATES
from .generators import VIDEO_PROFILES, IMAGE_PROFILES
from .workflow import Studio
from .knowledge import knowledge_catalog
from .creative import creative_schema
from .exports import export_editor
from .recipes import recipe_catalog
from .course_rules import course_coverage
from .paths import data_root as default_data_root, mcp_launch_configuration

def credential(root, filename):
    root.mkdir(parents=True, exist_ok=True)
    file = root / filename
    if not file.exists():
        try:
            with file.open('x', encoding='utf-8') as stream:
                stream.write(secrets.token_urlsafe(36))
        except FileExistsError:
            pass
    return file.read_text(encoding='utf-8').strip()


class Command(BaseModel):
    operation: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    actor: str = 'agent'


def create_app(data_root=None, agent_token=None, ui_token=None):
    root = Path(data_root or default_data_root()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    agent_token = agent_token or credential(root, 'agent.token')
    ui_token = ui_token or credential(root, 'browser.token')
    studio = Studio(root / 'workflow.db', root / 'media', root / 'inbox')
    providers = Providers(studio, root / 'connections.json')

    @asynccontextmanager
    async def lifespan(app):
        providers.reconcile()
        yield
        for task in list(providers.tasks):
            task.cancel()
        if providers.tasks:
            import asyncio
            await asyncio.gather(*providers.tasks, return_exceptions=True)

    app = FastAPI(title='Frame Studio MCP workflow', lifespan=lifespan)
    app.state.studio = studio
    app.state.providers = providers

    @app.exception_handler(StudioError)
    async def studio_error(request, exc):
        return JSONResponse({'error': exc.code, 'message': str(exc)}, status_code=exc.status)

    def authorize(request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        if secrets.compare_digest(token, ui_token):
            return True
        if secrets.compare_digest(token, agent_token):
            return False
        raise HTTPException(401, 'Studio connection token required.')

    @app.get('/health')
    def health():
        result = {'status': 'ok', 'service': 'frame-studio', 'schema_version': 2}
        if os.environ.get('STUDIO_DESKTOP_INSTANCE'):
            result['instance_id'] = os.environ['STUDIO_DESKTOP_INSTANCE']
        return result

    @app.get('/studio/v1/media/{project_id}/{filename}')
    def media(project_id: str, filename: str, request: Request):
        authorize(request)
        p = studio.get(project_id)
        asset = next((a for a in p['assets'] if Path(a['path']).name == filename), None)
        if not asset:
            raise StudioError('not_found', 'Media not found.', 404)
        path = Path(asset['path']).resolve()
        if not path.is_relative_to(studio.media_root) or not path.is_file():
            raise StudioError('not_found', 'Media not found.', 404)
        return FileResponse(path, media_type=asset['mime'])

    @app.post('/studio/v1/command')
    async def command(body: Command, request: Request):
        human = authorize(request)
        op, a = body.operation, body.arguments
        actor = 'user' if human else 'agent:' + body.actor[:94]
        if op == 'update_production' and isinstance(a.get('production'), dict) and any(k in a['production'] for k in ['resources', 'require_recorded_checks', 'recipe']) and not human:
            raise StudioError('human_only', 'Resource and quality policy belong to the user. Agents may report evidence and actual job costs.', 403)
        if op in ['set_policy', 'review', 'save_connection', 'delete_project', 'restore_project', 'list_deleted', 'save_project_template', 'rename_project_template', 'delete_project_template', 'update_batch', 'set_project_dispatch', 'sync_batch_identity', 'endorse_recipe'] and not human:
            raise StudioError('human_only', 'This control belongs to the user in the studio UI.', 403)
        if op == 'studio_capabilities':
            return {'server': 'Frame Studio', 'schema_version': 2, 'transport': 'stdio bridge',
                    'mcp_launch': mcp_launch_configuration(root),
                    'creative_schema': creative_schema(), 'knowledge_coverage': knowledge_catalog()['coverage'],
                    'execution_modes': ['agent_handoff', 'json_job_api'], 'flow_account': 'not_connected',
                    'connections': providers.public(), 'inbox': str(studio.inbox),
                    'video_profiles': VIDEO_PROFILES, 'image_profiles': IMAGE_PROFILES,
                    'steps': [{'id': s, 'name': l} for s, l in zip(STEPS, LABELS)], 'templates': TEMPLATES + studio.list_saved_templates()}
        if op == 'create_batch': return studio.create_batch(a['name'], a['idea'], a.get('kind', 'variations'), a.get('template_id', 'custom'), a.get('count', 5), a['request_id'], actor,
            policy=a.get('policy'), briefs=a.get('briefs'), allow_policy=human, identity_source_project_id=a.get('identity_source_project_id'), source_revision=a.get('source_revision'))
        if op == 'list_batches': return studio.list_batches()
        if op == 'get_batch': return studio.get_batch(a['batch_id'])
        if op == 'update_batch': return studio.update_batch(a['batch_id'], a['policy'], a['expected_revision'])
        if op == 'production_queue': return studio.production_queue(a.get('batch_id'))
        if op == 'claim_queue_task': return studio.claim_queue_task(actor, a['request_id'], a.get('batch_id'))
        if op == 'renew_queue_task': return studio.renew_queue_task(a['task_id'], actor)
        if op == 'finish_queue_task': return studio.finish_queue_task(a['task_id'], actor, a['status'], a.get('note', ''))
        if op == 'set_project_dispatch': return studio.set_project_dispatch(a['project_id'], a['paused'], a.get('priority', 0), a['expected_revision'])
        if op == 'sync_batch_identity': return studio.sync_batch_identity(a['batch_id'], a['source_project_id'], a['expected_revision'], a['source_revision'])
        if op == 'recipe_metrics': return studio.recipe_metrics(a['template_id'])
        if op == 'recipe_catalog':
            validation = studio.recipe_validation_summary()
            return {'recipes': [{**r, 'validation': validation.get(r['id'], {'reviewed_outputs': 0, 'passed_outputs': 0, 'ideas': 0, 'models': []})} for r in recipe_catalog()], 'coverage': course_coverage()}
        if op == 'recipe_trials': return studio.recipe_trials(a['project_id'])
        if op == 'record_recipe_trial': return studio.record_recipe_trial(a['project_id'], a['assessment'], a['expected_revision'], actor)
        if op == 'activate_recipe': return studio.activate_recipe(a['project_id'], a['expected_revision'], actor)
        if op == 'endorse_recipe': return studio.endorse_recipe(a['template_id'], a['project_id'], a['note'], a['expected_revision'], a['template_revision'], a.get('level', 'pilot'))
        if op == 'list_templates': return TEMPLATES + studio.list_saved_templates()
        if op == 'get_saved_template': return studio.get_saved_template(a['template_id'])
        if op == 'save_project_template': return studio.save_project_template(a['project_id'], a['name'], a.get('description', ''), a['sections'], a['expected_revision'], a.get('settings_shot_id', ''))
        if op == 'rename_project_template': return studio.rename_project_template(a['template_id'], a['name'], a.get('description', ''), a['expected_revision'])
        if op == 'delete_project_template': return studio.delete_project_template(a['template_id'], a['expected_revision'])
        if op == 'apply_project_template':
            if not human and isinstance(a.get('sections'), list) and 'workflow' in a['sections']:
                raise StudioError('human_only', 'Applying workflow approval/quality policy belongs to the user.', 403)
            return studio.apply_project_template(a['project_id'], a['template_id'], a['sections'], a['expected_revision'], a['template_revision'], actor)
        if op == 'knowledge_catalog': return knowledge_catalog(a.get('query', ''), a.get('category', ''))
        if op == 'creative_schema': return creative_schema()
        if op == 'update_production': return studio.update_production(a['project_id'], a['production'], a['expected_revision'], actor)
        if op == 'validate_project': return studio.validate_project(a['project_id'])
        if op == 'preview_shot': return studio.preview_shot(a['project_id'], a['shot_id'])
        if op == 'record_take_review': return studio.record_take_review(a['project_id'], a['asset_id'], a['review'], a['expected_revision'], actor)
        if op == 'select_take': return studio.select_take(a['project_id'], a['asset_id'], a['expected_revision'], actor)
        if op == 'revise_shot': return studio.revise_shot(a['project_id'], a['shot_id'], a['kind'], a['reason'], a['expected_revision'], actor)
        if op == 'extract_continuation': return studio.extract_continuation(a['project_id'], a['asset_id'], a['expected_revision'], actor)
        if op == 'repair_handoff': return studio.repair_handoff(a['project_id'], a['asset_id'], a['defect'], a.get('mask_asset_id', ''), a['expected_revision'], actor)
        if op == 'record_job_cost': return studio.record_job_cost(a['project_id'], a['job_id'], a['actual'], a['evidence'], a['expected_revision'], actor)
        if op == 'production_metrics': return studio.production_metrics(a['project_id'])
        if op == 'export_editor_package': return export_editor(studio, a['project_id'])
        if op == 'list_projects': return studio.list_projects()
        if op == 'create_project': return studio.create_project(a['name'], a.get('template_id', 'custom'), a.get('request_id'), actor, allow_template_policy=human)
        if op == 'duplicate_project': return studio.duplicate_project(a['project_id'], a.get('name'), actor)
        if op == 'delete_project': return studio.delete_project(a['project_id'], a['expected_revision'])
        if op == 'restore_project': return studio.restore_project(a['project_id'])
        if op == 'list_deleted': return studio.list_deleted()
        if op == 'export_handoff': return studio.export_handoff(a['project_id'])
        if op == 'get_project': return studio.get_project(a['project_id'])
        if op == 'next_action': return studio.next_action(a['project_id'])
        if op == 'update_settings': return studio.update_settings(a['project_id'], a['settings'], a['expected_revision'], actor)
        if op == 'update_shots': return studio.update_shots(a['project_id'], a['shots'], a['expected_revision'], actor)
        if op == 'complete_step': return studio.complete_step(a['project_id'], a['step'], a['output'], a['expected_revision'], actor)
        if op == 'claim_generation': return studio.claim_next(a['project_id'], actor, a['request_id'])
        if op == 'return_generation': return studio.return_result(a['job_id'], a['output_path'], actor)
        if op == 'get_job': return studio.find_job(a['job_id'])[1]
        if op == 'cancel_job': return studio.cancel_job(a['job_id'], actor)
        if op == 'import_reference': return studio.import_reference(a['project_id'], a['path'], a.get('name', 'Reference'), a['expected_revision'], actor, kind=a.get('kind', 'image'))
        if op == 'import_final': return studio.import_final(a['project_id'], a['path'], a['expected_revision'], actor)
        if op == 'editor_handoff': return studio.editor_handoff(a['project_id'])
        if op == 'set_policy': return studio.set_policy(a['project_id'], a['policy'], a['expected_revision'])
        if op == 'review': return studio.review(a['project_id'], a['step'], a['approve'], a.get('note', ''), a['expected_revision'])
        if op == 'save_connection': return providers.save(a)
        if op == 'run_provider': return providers.submit(a['job_id'], a['connection_id'])
        raise StudioError('unknown_operation', 'Unknown studio operation.')

    @app.get('/studio/v1/export/{project_id}/{filename}')
    def download_export(project_id: str, filename: str, request: Request):
        authorize(request)
        import re
        studio.get(project_id)
        if not re.fullmatch(r'[a-f0-9]{32}\.zip', filename):
            raise StudioError('not_found', 'Export not found.', 404)
        path = studio.media_root / project_id / 'exports' / filename
        if not path.is_file():
            raise StudioError('not_found', 'Export not found.', 404)
        return FileResponse(path, media_type='application/zip', filename='studio-generator-handoff.zip')

    @app.exception_handler(KeyError)
    async def missing_field(request, exc):
        return JSONResponse({'error': 'missing_argument', 'message': 'A required argument is missing: ' + str(exc)}, status_code=422)

    return app


def app_factory():
    return create_app()
