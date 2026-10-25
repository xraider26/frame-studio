import os
import secrets
import uuid
import json
import copy
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .handoffs import serialize_claim, serialize_job, serialize_capabilities
from .providers import Providers
from .store import StudioError
from .agent_rules import RULES_VERSION, validate_revision
from .templates import LABELS, STEPS, TEMPLATES
from .generators import VIDEO_PROFILES, IMAGE_PROFILES
from .workflow import Studio
from .knowledge import knowledge_catalog
from .creative import creative_schema
from .exports import export_editor
from .recipes import recipe_catalog
from .sequences import sequence_catalog
from .course_rules import course_coverage, source_catalog
from .comfy_export import export_comfy
from .paths import data_root as default_data_root, mcp_launch_configuration, resolve_writable_root
from .creator_chat import current_decision, prepare_decision, prior_decision, decision_scope, decision_project, decision_response, OPERATIONS

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


def create_app(data_root=None, agent_token=None, ui_token=None, bridge_token=None):
    root = resolve_writable_root(Path(data_root)) if data_root is not None else default_data_root()
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

    app = FastAPI(title='Orchestra MCP workflow', lifespan=lifespan)
    app.state.studio = studio
    app.state.providers = providers
    app.state.data_root = root

    @app.exception_handler(StudioError)
    async def studio_error(request, exc):
        return JSONResponse({'error': exc.code, 'message': str(exc)}, status_code=exc.status)

    def authorize(request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        if secrets.compare_digest(token, ui_token):
            return True
        if secrets.compare_digest(token, agent_token):
            return False
        if bridge_token and secrets.compare_digest(token, bridge_token):
            return False
        raise HTTPException(401, 'Studio connection token required.')

    @app.get('/health')
    def health():
        result = {'status': 'ok', 'service': 'frame-studio', 'schema_version': 2,
                  'data_root': str(root), 'service_pid': os.getpid()}
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
        authenticated_human = authorize(request)
        relay = current_decision()
        human = authenticated_human or bool(relay)
        op, a = body.operation, body.arguments
        actor = relay['actor'] if relay else 'user' if human else 'agent:' + body.actor[:94]
        if op == 'creator_decision':
            if relay:
                raise StudioError('invalid_creator_decision', 'Nested creator decisions are not supported.')
            decision = prepare_decision(a, body.actor)
            project = decision_project(studio, decision['project_id'])
            if prior_decision(project, decision):
                return decision_response(studio, decision)
            if project.get('deleted_at') and decision['operation'] != 'restore_project':
                raise StudioError('project_deleted', 'Restore this project before another decision.', 409)
            if project['revision'] != decision['expected_revision']:
                raise StudioError('revision_conflict', 'Refresh the target project before applying the creator instruction.', 409)
            if not authenticated_human and not project.get('deleted_at'):
                studio.require_workflow_contract(project['id'], 'agent:'+body.actor[:94])
            arguments = {**decision['arguments'], 'project_id': project['id'], 'expected_revision': decision['expected_revision']}
            if decision['operation'] == 'import_reference' and getattr(request.state, 'creator_reference_upload', None):
                arguments['path'] = request.state.creator_reference_upload
            object_revision = {'rename_project_template':'template_revision', 'delete_project_template':'template_revision', 'update_batch':'batch_revision', 'sync_batch_identity':'batch_revision'}.get(decision['operation'])
            if object_revision:
                validate_revision(arguments.get(object_revision))
                arguments['expected_revision'] = arguments.pop(object_revision)
            if decision['operation'] == 'request_revision':
                arguments['reason'] = decision['user_instruction']
            if decision['operation'] in {'update_batch', 'sync_batch_identity'}:
                batch = studio.get_batch(arguments.get('batch_id', ''))
                if project['id'] not in batch['project_ids'] and project['id'] != batch.get('identity_source_project_id'):
                    raise StudioError('decision_target', 'The decision project must belong to the target batch or be its canonical source.', 409)
                if decision['operation'] == 'sync_batch_identity' and arguments.get('source_project_id') != project['id']:
                    raise StudioError('decision_target', 'Name the actual canonical source as the decision project.', 409)
                decision['allowed_projects'] = set(batch['project_ids']) | {project['id']}
            external_result = None
            if decision['operation'] == 'validate_connection':
                connection_id = arguments['connection_id']
                before_connection = copy.deepcopy(providers.connections.get(connection_id))
                # This is a read-only remote capability probe. Never hold a
                # synchronous SQLite writer lock across its network await.
                external_result = await providers.validate_connection(connection_id)
                if providers.connections.get(connection_id) != before_connection:
                    raise StudioError('revision_conflict', 'Connection settings changed during validation; retry with current inputs.', 409)
            with decision_scope(decision, studio) as active_decision:
                if active_decision['replayed']:
                    return decision_response(studio, decision)
                result = external_result if decision['operation'] == 'validate_connection' else await command(Command(operation=decision['operation'], arguments=arguments, actor=body.actor), request)
                # Some equivalent creator controls operate outside a project
                # payload (saved templates/connections). Attribute their result.
                current = decision_project(studio, project['id'])
                if not prior_decision(current, decision):
                    studio.mutate(project['id'], current['revision'], lambda p: None, allow_deleted=True)
                return decision_response(studio, decision, result, save_result=True)
        if op == 'update_production' and isinstance(a.get('production'), dict) and any(k in a['production'] for k in ['resources', 'require_recorded_checks', 'recipe']) and not human:
            raise StudioError('human_only', 'Resource and quality policy belong to the user. Agents may report evidence and actual job costs.', 403)
        if op in ['review_calibration', 'set_calibration_mode', 'configure_calibration', 'validate_connection', 'export_comfy_handoff', 'apply_sequence', 'set_policy', 'review', 'save_connection', 'delete_project', 'restore_project', 'list_deleted', 'save_project_template', 'rename_project_template', 'delete_project_template', 'update_batch', 'set_project_dispatch', 'sync_batch_identity', 'endorse_recipe', 'activate_recipe', 'record_recipe_trial'] and not human:
            raise StudioError('human_only', 'This control belongs to the user in the studio UI.', 403)
        if op == 'apply_project_template' and not human and isinstance(a.get('sections'), list) and 'workflow' in a['sections']:
            raise StudioError('human_only', 'Applying workflow approval/quality policy belongs to the user.', 403)
        project_writes = {'apply_project_template', 'update_production', 'record_take_review', 'select_take', 'revise_shot', 'extract_continuation', 'repair_handoff', 'record_job_cost', 'record_import_cost', 'duplicate_project', 'update_settings', 'update_shots', 'complete_step', 'claim_generation', 'import_reference', 'import_external_take', 'import_final'}
        revision_writes = project_writes - {'duplicate_project'}
        if not human and op in {'apply_project_template', 'update_settings'}:
            studio.require_generation_setup(a['project_id'])
        if not human and op in project_writes:
            studio.require_workflow_contract(a['project_id'], actor)
            if op in revision_writes:
                validate_revision(a.get('expected_revision'))
        if not human and op in {'return_generation', 'run_provider', 'cancel_job'}:
            project, job = studio.find_job(a['job_id'])
            if job['actor'] != actor:
                raise StudioError('job_owner', 'Only the claiming executor may return, run or cancel this job. Read get_job and coordinate with its owner.', 403)
            if op != 'return_generation':
                studio.require_workflow_contract(project['id'], actor)
        if not human and op == 'finish_queue_task':
            with studio.connect() as conn:
                row = conn.execute('SELECT project_id FROM studio_tasks WHERE id=?', (a['task_id'],)).fetchone()
            if row:
                studio.require_workflow_contract(row[0], actor)
        if op == 'start_project_setup': return studio.start_project_setup(a.get('project_id'), a.get('output_type'))
        if op == 'review_calibration': return studio.review_calibration(a['project_id'], a['asset_id'], a['approve'], a.get('note', ''), a.get('expected_revision'), actor)
        if op == 'set_calibration_mode': return studio.set_calibration_mode(a['project_id'], a['mode'], a.get('expected_revision'), actor)
        if op == 'configure_calibration': return studio.configure_calibration(a['project_id'], a['representative_shot_id'], a['scope'], a.get('expected_revision'), actor)
        if op == 'set_generation_setup': return studio.set_generation_setup(a['project_id'], a['setup'], a.get('expected_revision'), actor)
        if op == 'get_workflow_contract': return studio.get_workflow_contract(a['project_id'], a.get('detail', 'summary'))
        if op == 'acknowledge_workflow_contract': return studio.acknowledge_workflow_contract(a['project_id'], a['contract_version'], a.get('expected_revision'), actor)
        if op == 'studio_capabilities':
            capabilities = {'server': 'Orchestra', 'schema_version': 2, 'rules_version': RULES_VERSION, 'agent_contract_required': True, 'initial_action': studio.start_project_setup(), 'agent_bootstrap': ['start_project_setup', 'studio_capabilities', 'get_project', 'get_workflow_contract', 'acknowledge_workflow_contract', 'next_action'], 'transport': 'stdio bridge', 'creator_decisions': {'tool': 'creator_decision', 'authority': 'user_instruction_relayed', 'operations': sorted(OPERATIONS)},
                    'mcp_launch': mcp_launch_configuration(root),
                    'creative_schema': creative_schema(), 'knowledge_coverage': knowledge_catalog()['coverage'],
                    'execution_modes': ['agent_handoff', 'json_job_api', 'comfyui'], 'flow_account': 'not_connected',
                    'connections': providers.public(), 'inbox': str(studio.inbox),
                    'video_profiles': VIDEO_PROFILES, 'image_profiles': IMAGE_PROFILES,
                    'output_types': ['image', 'video'], 'steps_by_output_type': {'image': ['brief', 'script', 'visual_direction', 'final_review'], 'video': STEPS},
                    'steps': [{'id': s, 'name': l} for s, l in zip(STEPS, LABELS)], 'templates': TEMPLATES + studio.list_saved_templates()}
            return serialize_capabilities(capabilities, a.get('detail', 'summary'))
        from .generation_setup import setup_from_explicit_settings
        if op == 'create_batch': return studio.create_batch(a['name'], a['idea'], a.get('kind', 'variations'), a.get('template_id', 'custom'), a.get('count', 5), a['request_id'], actor,
            policy=a.get('policy'), briefs=a.get('briefs'), allow_policy=human, identity_source_project_id=a.get('identity_source_project_id'), source_revision=a.get('source_revision'), output_type=a.get('output_type', 'video'), settings=a.get('settings'), generation_setup=a.get('generation_setup') if a.get('generation_setup') is not None else setup_from_explicit_settings(a.get('settings')))
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
            return {'recipes': [{**r, 'validation': validation.get(r['id'], {'reviewed_outputs': 0, 'passed_outputs': 0, 'ideas': 0, 'models': []})} for r in recipe_catalog(**{k: a[k] for k in ('recipe_id', 'stage', 'role', 'detail', 'include_provenance', 'offset', 'limit') if k in a})], **({'coverage': course_coverage()} if a.get('include_provenance') else {})}
        if op == 'sequence_catalog': return sequence_catalog(**{k: a[k] for k in ('sequence_id', 'stage', 'role', 'detail', 'include_provenance', 'offset', 'limit') if k in a})
        if op == 'source_catalog': return source_catalog(**{k: a[k] for k in ('source_id', 'recipe_id', 'stage', 'role', 'detail', 'include_provenance', 'offset', 'limit') if k in a})
        if op == 'get_context': return studio.get_context(a['context_id'], a['version'])
        if op == 'preview_sequence': return studio.preview_sequence(a['project_id'], a['sequence_id'])
        if op == 'apply_sequence': return studio.apply_sequence(a['project_id'], a['sequence_id'], a['expected_revision'], a.get('confirm_replace', False), actor)
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
        if op == 'request_revision': return studio.request_revision(a['project_id'], a.get('shot_id'), a.get('asset_id'), a.get('kind', 'image'), a['reason'], a['expected_revision'], actor)
        if op == 'extract_continuation': return studio.extract_continuation(a['project_id'], a['asset_id'], a['expected_revision'], actor)
        if op == 'repair_handoff': return studio.repair_handoff(a['project_id'], a['asset_id'], a['defect'], a.get('mask_asset_id', ''), a['expected_revision'], actor)
        if op == 'record_job_cost': return studio.record_job_cost(a['project_id'], a['job_id'], a['actual'], a['evidence'], a['expected_revision'], actor)
        if op == 'record_import_cost': return studio.record_import_cost(a['project_id'], a['asset_id'], a['actual'], a['evidence'], a['expected_revision'], actor)
        if op == 'production_metrics': return studio.production_metrics(a['project_id'])
        if op == 'export_editor_package': return export_editor(studio, a['project_id'])
        if op == 'list_projects': return studio.list_projects()
        if op == 'create_project': return studio.create_project(a['name'], a.get('template_id', 'custom'), a.get('request_id'), actor, allow_template_policy=human, output_type=a.get('output_type', 'video'), settings=a.get('settings'), generation_setup=a.get('generation_setup') if a.get('generation_setup') is not None else setup_from_explicit_settings(a.get('settings')))
        if op == 'duplicate_project': return studio.duplicate_project(a['project_id'], a.get('name'), actor, adopt_generation_setup=True)
        if op == 'delete_project': return studio.delete_project(a['project_id'], a['expected_revision'])
        if op == 'restore_project': return studio.restore_project(a['project_id'])
        if op == 'list_deleted': return studio.list_deleted()
        if op == 'export_handoff': return studio.export_handoff(a['project_id'])
        if op == 'get_project': return studio.get_project(a['project_id'], a.get('detail', 'summary'))
        if op == 'next_action': return studio.next_action(a['project_id'])
        if op == 'update_settings': return studio.update_settings(a['project_id'], a['settings'], a['expected_revision'], actor)
        if op == 'update_shots': return studio.update_shots(a['project_id'], a['shots'], a['expected_revision'], actor)
        if op == 'complete_step': return studio.complete_step(a['project_id'], a['step'], a['output'], a['expected_revision'], actor)
        if op == 'claim_generation': return serialize_claim(studio.claim_next(a['project_id'], actor, a['request_id'], a.get('expected_revision')), a.get('response_format', 'compact'))
        if op == 'record_generation_execution': return studio.record_generation_execution(a['job_id'], a['execution'], a['expected_revision'], actor)
        if op == 'return_generation': return studio.return_result(a['job_id'], a['output_path'], actor)
        if op == 'get_job': return serialize_job(studio.find_job(a['job_id'])[1], a.get('detail', 'summary'))
        if op == 'cancel_job': return studio.cancel_job(a['job_id'], actor)
        if op == 'import_reference': return studio.import_reference(a['project_id'], a['path'], a.get('name', 'Reference'), a['expected_revision'], actor, kind=a.get('kind', 'image'), entity_id=a.get('entity_id'))
        if op == 'import_external_take': return studio.import_external_take(a['project_id'], a['expected_revision'], a['shot_id'], a['output_path'], a['kind'], actor, a.get('metadata'))
        if op == 'import_final': return studio.import_final(a['project_id'], a['path'], a['expected_revision'], actor)
        if op == 'editor_handoff': return studio.editor_handoff(a['project_id'])
        if op == 'set_policy': return studio.set_policy(a['project_id'], a['policy'], a['expected_revision'])
        if op == 'review': return studio.review(a['project_id'], a['step'], a['approve'], a.get('note', ''), a['expected_revision'])
        if op == 'save_connection': return providers.save(a)
        if op == 'validate_connection': return await providers.validate_connection(a['connection_id'])
        if op == 'export_comfy_handoff': return export_comfy(studio, providers, a['project_id'], a['connection_id'])
        if op == 'run_provider': return providers.submit(a['job_id'], a['connection_id'])
        raise StudioError('unknown_operation', 'Unknown Orchestra operation. Read studio_capabilities for supported tools, then get_workflow_contract and next_action for the project.')

    @app.post('/studio/v1/jobs/{job_id}/output')
    async def upload_job_output(job_id: str, request: Request):
        human = authorize(request)
        async with request.form() as form:
            actor = 'user' if human else 'agent:'+str(form.get('actor', 'upload'))[:94]
            project, job = studio.find_job(job_id)
            if job['actor'] != actor:
                raise StudioError('job_owner', 'Only the claiming executor may upload this output.', 403)
            if job['status'] in {'canceled', 'failed', 'interrupted'}:
                raise StudioError('job_closed', 'This generation job is closed.', 409)
            file = form.get('file')
            if not file or not hasattr(file, 'read'):
                raise StudioError('missing_upload', 'Provide the generated image or video.')
            suffix = Path(str(getattr(file, 'filename', ''))).suffix.lower()
            allowed = {'.png', '.jpg', '.jpeg', '.webp'} if job['kind'] == 'image' else {'.mp4'}
            if suffix not in allowed:
                raise StudioError('invalid_asset', 'Upload the media type requested by this job.')
            path = studio.inbox / ('upload-'+uuid.uuid4().hex+suffix)
            try:
                with path.open('xb') as stream:
                    size = 0
                    while chunk := await file.read(1024*1024):
                        size += len(chunk)
                        if size > 500*1024*1024:
                            raise StudioError('upload_too_large', 'Generated output must be at most 500 MB.', 413)
                        stream.write(chunk)
                return studio.return_result(job_id, str(path), actor)
            finally:
                path.unlink(missing_ok=True)
                await file.close()

    @app.post('/studio/v1/creator-reference')
    async def upload_creator_reference(request: Request):
        human = authorize(request)
        async with request.form() as form:
            try:
                payload = json.loads(str(form.get('decision', '')))
            except (ValueError, TypeError) as exc:
                raise StudioError('invalid_creator_decision', 'Provide the explicit reference instruction and target.') from exc
            actor = str(form.get('actor', 'upload'))[:94]
            decision = prepare_decision(payload, actor)
            if decision['operation'] != 'import_reference':
                raise StudioError('invalid_creator_decision', 'This endpoint only imports the requested reference.')
            project = studio.get(decision['project_id'])
            if not prior_decision(project, decision):
                if project['revision'] != decision['expected_revision']:
                    raise StudioError('revision_conflict', 'Refresh before uploading the requested reference.', 409)
                if not human:
                    studio.require_workflow_contract(project['id'], 'agent:'+actor)
            file = form.get('file')
            if not file or not hasattr(file, 'read'):
                raise StudioError('missing_upload', 'Provide the requested reference file.')
            suffix = Path(str(getattr(file, 'filename', ''))).suffix.lower()
            if suffix not in {'.png', '.jpg', '.jpeg', '.webp', '.mp4'}:
                raise StudioError('invalid_asset', 'Use an image or MP4 reference.')
            path = studio.inbox / ('upload-reference-'+uuid.uuid4().hex+suffix)
            try:
                with path.open('xb') as stream:
                    size = 0
                    while chunk := await file.read(1024*1024):
                        size += len(chunk)
                        if size > 500*1024*1024:
                            raise StudioError('upload_too_large', 'Reference must be at most 500 MB.', 413)
                        stream.write(chunk)
                request.state.creator_reference_upload = str(path)
                return await command(Command(operation='creator_decision', arguments=payload, actor=actor), request)
            finally:
                path.unlink(missing_ok=True)
                await file.close()

    @app.post('/studio/v1/upload')
    async def upload(request: Request):
        human = authorize(request)
        async with request.form() as form:
            actor = 'user' if human else 'agent:' + str(form.get('actor', 'upload'))[:94]
            file = form.get('file')
            if not file or not hasattr(file, 'read'):
                raise StudioError('missing_upload', 'Choose a media file.')
            try:
                revision = int(form.get('expected_revision', ''))
            except (ValueError, TypeError):
                raise StudioError('invalid_revision', 'Provide the current project revision.')
            project_id = str(form.get('project_id', ''))
            if not human:
                studio.require_workflow_contract(project_id, actor)
            role = str(form.get('role', 'reference'))
            kind = str(form.get('kind', 'image'))
            if role not in ['reference', 'take', 'final']:
                raise StudioError('invalid_upload', 'Choose reference, take or final media.')
            suffix = Path(str(getattr(file, 'filename', ''))).suffix.lower()
            path = studio.inbox / (uuid.uuid4().hex + suffix)
            try:
                with path.open('wb') as stream:
                    size = 0
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > 512 * 1024 * 1024:
                            raise StudioError('upload_too_large', 'Media upload must be at most 512 MB.', 413)
                        stream.write(chunk)
                if role == 'reference':
                    return studio.import_reference(project_id, str(path), str(form.get('name', getattr(file, 'filename', 'Reference'))), revision, actor, kind=kind, entity_id=form.get('entity_id') or None)
                if role == 'take':
                    metadata = {key: str(form[key]) for key in ['generator', 'prompt'] if form.get(key)}
                    return studio.import_external_take(project_id, revision, str(form.get('shot_id', '')), str(path), kind, actor, metadata)
                return studio.import_final(project_id, str(path), revision, actor)
            finally:
                path.unlink(missing_ok=True)
                await file.close()

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
