# Orchestra: agent-controlled workflow

Image generation/editing requirements and direct ComfyUI workflow execution are documented in [ComfyUI and image prompting](COMFYUI.md). Agents use the existing owned `claim_generation` → `run_provider` → `get_job` flow; connections and workflow validation/export are human UI controls. Read compiler warnings and `remote_prompt_id` before retrying interrupted ComfyUI work.

## Strict agent contract (next-beta source)

### Windows connection and copying configuration (0.3.1)

In the desktop Orchestra menu, choose **Copy MCP configuration → Codex (TOML)**, **Cursor (JSON)**, **Claude Desktop (JSON)** or **Antigravity (JSON)**. The command is taken from the installed resources directory, including custom/nested installation paths; arguments preserve the existing data directory. Existing stale client commands are not rewritten automatically: replace the Orchestra entry with the freshly copied configuration, then reconnect the client.

The desktop service publishes a private per-user connection under `~/.orchestra/desktop-connections/`, outside Windows' virtualized AppData folders. It contains a separate, per-launch agent credential, never the browser credential. Treat these files as secrets; do not upload or commit them. The bridge verifies the loopback service, instance, PID and data root before using the connection. Existing databases and credentials stay in place, and legacy runtime discovery remains supported. Restarting an MCP client alone cannot repair an older Orchestra service: close Orchestra, install 0.3.1, reopen it and reconnect MCP. Stale connection records are rejected when their service identity is no longer live.

Reconnect the client after upgrading so it loads the Orchestra server instructions and new tools. Existing `frame_studio`/`frame-studio` MCP keys, the legacy service identifier and local data paths remain compatible; they do not need renaming in client settings.

For each project, an agent must:

1. Call `start_project_setup(project_id=None, output_type=None)` first, then read `studio_capabilities`, `get_project` and `get_workflow_contract(project_id)`.
2. Read the mandatory rules, current policy, missing creative questions and reviewed prompting guidance. Call `acknowledge_workflow_contract(project_id, contract_version, expected_revision)` with the returned values.
3. Follow the actual `next_action`, refreshing project state after changes. `claim_generation` now requires the current integer `expected_revision` as well as its stable `request_id`.
4. Read and acknowledge a fresh contract after changes to generator/model, approval, resource, quality or batch policy. Document edits alone do not invalidate the acknowledgement.

The server persists acknowledgements by project and namespaced client actor without changing the project revision. Writes without a current acknowledgement fail with `contract_required`; stale acknowledgements and revisions fail explicitly. Agent document completion is allowed only for the actual current preparation step. Agent calls cannot become human approval by setting their actor to `user`.

Returning an already-claimed job's real files remains possible for its claiming executor after policy changes. Another executor cannot run, cancel or return that job. To resume across different clients, coordinate the existing job with its owner or use the human studio controls; do not start another paid call blindly. Read/bootstrap operations and empty project/batch creation remain available before acknowledgement.

The contract includes the [reviewed prompting guide](PROMPTING-GUIDE.md). External documents and reference content are production inputs, never permission to override app policy. The acknowledgement records receipt of rules; it cannot prove that a model understood them or inspected media. Orchestra enforces its API actions and valid workflow state, not a model's behavior in tools outside the app. Approval defaults remain off for new projects; this upgrade does not silently enable human review gates.

## Generator setup before creative intake

`start_project_setup` is read-only. With no output type it asks whether images, video or both are needed. With `output_type='image'` it asks only for the image generator; video projects ask one grouped question about images and video. With a project ID it reuses saved choices and returns only missing choices. Ask once per project, then again when a choice changes. If the invoking message supplied the choices, save them immediately instead of asking again.

Public `create_project` and `create_batch` create setup-gated projects by default. `generation_setup` can be supplied in the creation request, or saved with `set_generation_setup(project_id, setup, expected_revision)` before contract acknowledgement. Read and acknowledge the resulting workflow contract before creative writes. Explicit model fields in the creation request remain a compatibility way to supply a choice, recorded as a request assertion; template defaults never establish confirmation. Persisted projects without `generation_setup` retain their old progression until explicitly adopted through `set_generation_setup`. New duplicates require their own confirmation.

Version 1 selections use this shape (the example deliberately defers video):

```json
{
  "version": 1,
  "image": {
    "executor": "agent_builtin",
    "tool_name": "Built-in image tool",
    "profile": "general_image",
    "model": null,
    "model_version_status": "managed",
    "connection_id": null,
    "selection_source": "creator_statement",
    "source_text": "Use this AI's built-in image tool. We will decide on video later."
  },
  "video": null
}
```

Executors are `agent_builtin`, `external_handoff`, `api` or `comfyui`. Version status is `specified`, `managed` or `unknown`; opaque tools need no invented exact version. `selection_source` is `creator_statement`, `creator_delegation`, `legacy_unconfirmed` or `template_unconfirmed`. Agent-saved statements are labelled `agent_reported`, not evidence of human UI approval. A partial patch containing only `video` preserves the image selection. Stale or non-integer revisions are rejected atomically.

A null video choice remains visibly incomplete and blocks video generation while permitting image preparation/calibration. A named external handoff is a destination, not an API connection or evidence of capabilities. API/ComfyUI execution still requires a separately configured enabled connection and its normal execution checks. Record observations separately with `update_production` under `capabilities_by_kind.image` or `.video`; changing a selection clears only that medium's observation. Legacy `production.capabilities` is preserved but does not confirm either new selection. Changing old model/profile fields or applying changed template settings reopens the affected generator question. The selection fingerprint is part of the workflow contract.

The **Production settings → Observed generator capabilities** editor saves the same per-medium observations for adopted projects. Video projects offer an image/video observation selector; image-only projects expose only image observations. Legacy projects retain their combined capability editor. Take compatibility includes the relevant tool/executor/connection selection, so changing opaque tools cannot make an old-tool output current merely by reselecting it. Previously claimed outputs can still return as stale evidence.

The service advertises the initial question in MCP instructions and capabilities and blocks connected-agent creative writes/claims when their required selection is missing. It cannot force arbitrary third-party AI to ask conversational questions before tools, or control generation outside its boundary. Acknowledging rules and naming a tool do not prove access, media inspection or creator approval.

## Creative production upgrade (schema v2)

The studio now shares structured story/bible/shot direction with its agents. See [feature and source coverage](CREATIVE-COVERAGE.md) for exact capabilities, tests and current limits.

- `creative_schema`: field definitions, validation and inheritance rules. Shot `direction` includes camera/composition, lighting, art, action/states, sound, exact references and quality criteria; `edit_duration_seconds` and `edit_in_seconds` are separate from generation duration.
- `knowledge_catalog(query, category)`: searchable technique explanations, generated stills/spatial demonstrations, use cases, risks, source/provenance and editable `apply` patches. Coverage distinguishes studio-authored examples, the supplied playbook and selected verified original pages from a complete course catalogue import.
- `update_production`: patch structured brief/story/bible/defaults/capability observations and experiments. Resource policy and the required-QC switch remain human-only. Omit those fields in agent updates.
- `preview_shot` and `validate_project`: same compiler and deterministic checks used by browser and generation handoffs. A blank shot field inherits project direction. Generator/profile changes do not create an account connection.
- `record_take_review`: actual inspection evidence with `criteria: {text: true/false}`, `inspected: [image]` or `[beginning,middle,end]`, `notes` and `defect`. Required criteria arrive in `handoff.required_media_checks`. Agent actor names are prefixed `agent:`. Evidence never grants human approval.
- `select_take`, `revise_shot`: explicit compatible take selection or targeted image/video revision with a named reason. Unrelated selections remain; linked dependencies/review stages reopen. Old media is retained.
- `extract_continuation`: real local near-final-frame extraction; explicitly bind and inspect the resulting image. `repair_handoff` supplies original/mask/defect/preservation data for an external editor; it does not execute inpainting.
- `record_job_cost`: actual cost plus evidence in the project's single unit, retaining correction history. `production_metrics` reports known reserved/spent costs and unknown jobs. A claim reserves evidenced planned cost once; unknown costs or an exhausted hard limit block additional generation. Cancellation is not a refund.
- `export_editor_package`: selected actual MP4s plus editor JSON and source/timeline CSV; no native editor-project or rendered-video claim.

Additional `next_action` states: `resolve_preflight`, `resolve_resources` and `record_quality`. Resolve the stated inputs/evidence or let the user adjust their policy; do not bypass them. `await_approval` still means stop for the user's browser review.

New custom-template placeholders: `{environment} {mood} {opening} {ending} {dialogue} {composition} {body_look} {state_before} {state_after} {references}`. Existing placeholders remain accepted. The ZIP now includes structured production, direction, preflight/source coverage and technique data alongside compiled prompts and portable references.

Existing project IDs and documents remain intact. Older clients that omit `direction` retain that shot's saved nested data. Existing databases receive a one-time `*.pre-creative-v2.sqlite3` backup before upgrading persisted projects. These local private files remain excluded from Git.

This is the connected application at **http://127.0.0.1:3000/studio**. The earlier port-52741 HTML preview remains a separate prototype. Frame's real projects, generation tasks and imported media are stored locally in `studio_data/`. The existing companion dashboard, backend and media are preserved.

## Start

For the installed app, launch **Orchestra** from its shortcut. It starts its bundled services on available loopback ports. See [Windows setup](WINDOWS.md).

For a source checkout, run `./launch-studio.ps1` from that checkout's root. It starts the workflow API on port 8010 and frontend on port 3000 in hidden background processes. Logs are in the project directory. Run `./launch-studio.ps1 -BackendOnly` if the UI is already running. The legacy companion API on port 8000 is separate.

If dependencies need installing:

```powershell
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-studio.txt
```

Install frontend dependencies using its package lock if they are missing. FFmpeg/FFprobe must be in PATH to validate returned MP4 videos. No generation API key is required for planning or the agent handoff mode. A local or remote generation tool must be available separately to create real media.

## Connect your agent

Open **Connections & MCP**, choose your client format and copy the generated configuration for your own installation. The installed app uses its bundled service executable; a source checkout uses its actual Python/script paths. The [static examples](../configs/README.md) illustrate formats only. Merge the `frame_studio` entry into existing settings without replacing other servers. No credential needs copying: the bridge reads the local agent token. `STUDIO_CLIENT_NAME` identifies the client in activity.

- **Codex:** copy the studio's generated TOML entry into the client's MCP configuration using Codex Settings → MCP servers, or its trusted-project/user `config.toml` workflow. Restart/reconnect and inspect available tools. See https://developers.openai.com/codex/mcp.
- **Cursor:** merge the JSON entry into workspace `.cursor/mcp.json` or add it through MCP settings. See https://cursor.com/docs/mcp.
- **Claude Code:** use the generated JSON entry through the client's supported MCP setup, with the actual command/arguments from your studio. See https://code.claude.com/docs/en/mcp.
- **Antigravity:** add the JSON entry through Manage MCP Servers / raw configuration. The relevant setting differs between IDE, app and CLI; see https://antigravity.google/docs/mcp.
- **Claude Desktop:** use the same JSON server entry in its supported local MCP server configuration and restart it. This is a desktop server, not a public remote connector.

Use the entry generated by your running installation, rather than the placeholder paths in this repository. Verification of the MCP protocol and SDK bridge does not mean every installed client has already been configured. Existing client/global settings are not modified by this project.

## The agent loop

1. Call `start_project_setup` before creative questions, save the creator's generator choices, then read capabilities and create or open a project. Reuse the choices across sessions. `get_project` returns its saved revision, approval policy and next action; read and acknowledge its workflow contract before writing.
2. Write the actual brief and script through `complete_step`. Set creative controls and the ordered shots. User-defined review steps return `await_approval`; stop there and let the user review in the studio.
3. When `next_action` is `generate`, call `claim_generation` with a unique request ID. Reuse it only when retrying that exact call. The result includes the immutable prompt/reference/settings snapshot, job ID and local return inbox.
4. If `already_claimed` is true, inspect the job; do not initiate a second paid generation. Resume an unfinished handoff only when you know the previous executor has stopped. Cancel a waiting handoff before explicitly retrying failed external work.
5. Use a generation tool the user has actually authorized and connected. Save the actual PNG/JPEG/WebP or MP4 into the returned `return_inbox`. Handoffs include local reference image paths; reading them requires the client's local file/tool access.
6. Call `return_generation(job_id, output_path)`. The studio validates the media, copies it into the project as a new take, records provenance and returns the next action. Duplicate returns do not create extra takes. Outputs for changed prompts are retained as stale and cannot complete the current revision.
7. Continue until a human approval is required, an actual external edit is needed, or the workflow finishes. After production, get `editor_handoff` for the ordered take paths and editing notes. Return the actual external edit with `import_final`.

Example request:

> Use Orchestra to prepare a six-shot short drama about a traveler entering an abandoned observatory. Follow its workflow and review policy. When generation is available, get the handoff, generate using my connected local tool, return each output to the studio, and continue to the next permitted step.

The studio does not supply a generation model through MCP, borrow client subscriptions, or access Google Flow automatically. An agent without image/video tools can still plan, get prompts, import supplied outputs and track reviews.

## Approval controls

Every workflow step has an **Approval required** checkbox in Workflow & approvals. In the next-beta source, new projects start with every approval off; existing projects preserve their policy. On means the studio waits for an explicit browser review. Off means valid outputs allow automatic progression, visibly recorded as `auto_proceeded`, never human approval. Agents cannot turn off review or approve through the MCP tools. Enabling review again reopens the current review and dependent steps. Changes to source material invalidate affected progression; old media and decisions remain in activity/history.

The workflow is Brief → Script → Visual direction → Pilot → Production → Editor handoff → Final review. Visual direction requires one real image per shot; pilot requires the first shot's video; production requires videos for the remaining shots. The three shots in templates are editable starting points, not a generation/concurrency limit. The current shot list supports 1–200 planned shots. Agent handoffs are sequential next-action tasks; provider parallelism is not promised.

## Export without generation APIs

Open **Generator handoff**, choose **External agent / export**, select the video and image prompt profiles, and apply the choices. **Prepare export package** creates a real ZIP; **Download handoff ZIP** saves it. You can give the file to your Flow agent or another generator agent.

Profiles currently include Google Flow/Veo, Runway image-to-video, Runway text-to-video, general/Runway image prompts and custom templates. They change actual prompt content, not just a label. Custom templates accept the documented simple placeholders. Generator capabilities and supported clip durations still depend on the selected model; a profile does not connect or authenticate an account.

The ZIP contains portable `manifest.json`, `prompts.md`, `README.txt` and available reference/keyframe images. It carries project/shot IDs, source revision, intended settings, output filenames and review policy. It is not native Flow/Runway project format and does not contain an automatically rendered video. The receiving agent should check live studio state, claim each permitted task and return actual files through MCP; offline-generated files can be returned when connected again. An exported snapshot cannot override later prompt changes or review requirements.

## Duplicate, delete and restore

The buttons under the project dropdown provide **Duplicate**, **Delete** and **Trash**. Duplicate copies the plan, documents, generator choices and reference images to new IDs. Generated takes, jobs and approval decisions start fresh; next-beta duplicates start with approval off on each step. Delete is recoverable: the project goes to Trash and media stays on disk. Trash offers **Restore project**. The app does not expose permanent file deletion. Projects with an active API job must finish it before being moved to Trash.

## API-based generators

The alternative is a user-configured **JSON Job API** connection in Connections & MCP. This is an adapter contract, not a claim that vendor endpoints such as Gemini, Replicate, Fal or OpenAI accept this payload directly. A provider-specific adapter translates their request/response shapes into this contract. Users can host such an adapter locally or at their own HTTPS endpoint.

The backend POSTs the full handoff to `BASE_URL/generate`. It optionally sends the saved key as `Authorization: Bearer ...`. The response is either:

```json
{"status":"succeeded","output":{"base64":"BASE64_MEDIA_BYTES","mime_type":"image/png"}}
```

or an asynchronous response:

```json
{"status":"running","job_id":"provider-job-id"}
```

For an asynchronous response, GET `BASE_URL/jobs/provider-job-id` must return queued/running with that ID until succeeded. Accepted image MIME types: `image/png`, `image/jpeg`, `image/webp`; video: `video/mp4`. Actual media is verified after decoding. URL-only results are deliberately unsupported until an adapter handles provider downloads. Polling times out after about two minutes plus request time; failures are explicit and do not fabricate outputs. Check the provider before retrying because accepted calls may still be billed or finish there after a local failure.

Save and enable the connection, then claim a generation handoff and call `run_provider(job_id, connection_id)` or use Generate via API in the UI. The server owns the asynchronous task; poll `get_job`. Each connection has a cumulative user-set maximum request count. This limits submissions, not monetary cost. Updating the maximum does not reset used requests. Provider keys stay in backend `studio_data/connections.json`, which is ignored by Git and must be kept private; they are never returned by capabilities, tool results or the browser UI. Disabling a connection prevents new submissions.

## Limits and data

- Files need local disk storage; cloud media hosting is not required. Local returns must be inside the configured inbox or studio media directory and below 500 MB per file. The initial JSON connector limits encoded outputs to about 67 MB decoded.
- A local backend restart preserves external waiting handoffs. It marks in-progress API jobs interrupted rather than auto-resubmitting potentially paid calls.
- Only one next generation task is claimable per workflow position. An agent must return a shot before receiving the next one. It can perform its own internal generation variations, then return its chosen real output.
- Importing references changes creative inputs and reopens dependent output/review steps. Different take files are never overwritten.
- The new workflow SQLite DB is separate from legacy `backend/studio.db`. No legacy migration occurs and no prototype browser state is silently imported.
- Loopback credentials distinguish browser review controls from MCP calls. This is a workflow boundary, not protection against a malicious local administrator with filesystem access.
- No account connection, paid generation call, cloud upload or client-global configuration change is performed by merely starting this studio.

## Verification

Backend behavior suite, from the `backend` directory: `.venv/Scripts/python.exe -m unittest discover -s tests -v`. Live MCP/browser verification scripts use an isolated `.studio-test` database and fixture media. Test images are explicitly synthetic fixtures, not AI-generated output.

Motion-source references: call `import_reference` with `kind="video"` for an actual MP4 in the inbox, then bind its asset ID with role `motion` and pose/framing compatibility notes. Image imports retain the default `kind="image"`. Video references are excluded from image-generation inputs. Portable ZIPs include accepted bound media and per-shot `reference_files` mappings.

## Reusable workflow templates

For the installed Windows app, use **Connections & MCP** or **Orchestra → Copy MCP configuration**. Its command points to the bundled `FrameStudioService.exe` and explicit per-user data directory. Keep the desktop app open; no Python installation or source-checkout path is needed. Source-checkout configuration is also generated dynamically from its running Python executable and actual data root. See [Windows installation](WINDOWS.md).

Built-in formats now expose versioned course-informed production recipes. `recipe_catalog` returns their reference/planning/role/QC contracts, illustrative image metadata, source coverage and historical human video-trial summaries. `get_project`, compiled generation handoffs and queue tasks carry the active recipe context; generator ZIPs include readable and JSON recipe files. `recipe_trials` reads human final-production evidence. Recipe activation and recording final assessments remain human UI operations. See [production recipes](COURSE-RECIPES.md) for scope and limitations.

In Template library, save a named snapshot of selected creative settings, workflow/quality gates, and/or story and shot plan. A successful shot can supply the reusable camera, lighting and art defaults. Notes record what worked. Use a saved template in the new-project picker or apply selected sections to the current project. Rename/delete manage library entries independently of existing projects. Templates live in the same local SQLite database and survive restarts and deletion of the source project.

MCP: `list_templates` includes built-in and saved IDs, `get_saved_template` reads saved snapshots, `create_project` accepts a saved ID, and `apply_project_template` accepts `settings` and/or `story` with both project and template revisions. Saving/renaming/deleting templates and applying workflow policy are human UI controls. Agent-created projects retain default approval/quality policy. Story application replaces shots and prepared documents, reconciling references into the replaced cast/shot plan; affected outputs reopen, original media is retained. Snapshots omit reference file bindings (reattach them), output takes, completed approvals, spending settings/history, observed capabilities and experiment results.

## Batch production and queue workers

See `docs/PRODUCTION-SCALE.md` for the full workflow and limits. MCP tools: `create_batch`, `production_queue`, `get_batch`, `claim_queue_task`, `renew_queue_task`, `finish_queue_task`, and `recipe_metrics`. `create_batch` queues actual independent planning projects from an idea; it does not invent completed scripts/media. Claim work with a unique stable request ID, refresh the project, execute its real next action, and renew a 15-minute lease during long work. Finish after meaningful recorded progress or block with a real reason. User approval waits must be respected. Queue policy, pause/priority, identity sync and recipe endorsements are human controls in the UI. Batch caps also govern direct generation/provider starts.

## Sequence planning (next-beta source)

`sequence_catalog` lists seven creator/filmmaker patterns; `preview_sequence` accepts `project_id` and `sequence_id` and returns allocation, source revision and replacement warnings without changing the project. `apply_sequence` is human-only. Read the preview and help the creator choose a pattern in **Plan → Sequences**, then refresh project state before continuing. Coverage/audio intent is included in handoffs; editing techniques are instructions for external software. See [templates and sequences](TEMPLATES-AND-SEQUENCES.md).


### Exact generation execution evidence

After claiming, call `record_generation_execution(job_id, execution, expected_revision)` for the exact request actually supplied to the authorized generator. `execution` contains `tool`, unmodified `prompt`, `negative_prompt` (empty only when actually absent), ordered actual `references` (`id`, integer `version`, `slot`) and `arguments`. Keep unsupported native constraints disclosed in `unsupported_constraints`. Reference paths/native uploads in known argument schemas must agree with the bound reference versions. Agent reports are labeled `agent_reported`; only server adapters can create `server_recorded` evidence. The service hashes and preserves the request; a different report cannot overwrite it. Ownership and the current integer revision are required even when recording after media return.

Only line-ending differences normalize automatically. Added prose, reordered text, whitespace changes, omitted exclusions and reference-version changes remain mismatches; no semantic equivalence is inferred. The image generation tool supports prompt, actual references and transparency, with no exposed model or separate negative argument. Never invent those arguments or silently translate compiler exclusions into new visual prose. Revise saved inputs, claim anew and renew applicable calibration decisions when material content must change.

JSON and ComfyUI adapters record their exact submitted payload automatically, including ComfyUI's final bound workflow and uploaded-reference map. Required pre-generation execution rules are checked before provider dispatch. Existing owned files remain returnable after policy/input changes. Missing or mismatched evidence preserves the media and marks the job/take `needs_review`; this cannot satisfy the accepted baseline. Missing evidence may be reported later by the owner; a mismatched submitted request requires revised inputs and a new claim. Legacy stored v2 handoffs are not rewritten or backfilled with invented evidence: their absent contract/evidence is explicitly unavailable.

### Compact transport (schema 3)

`claim_generation` defaults to `response_format="compact"`. Read `job.id` and the single **top-level `handoff`**; `job.handoff` is absent. Explicit `response_format="legacy"` preserves the original response shape. Stable request IDs preserve ownership and idempotency in both formats. Stored v2 job snapshots are never rewritten.

`get_project` and `get_job` default to `detail="summary"`. Fetch `get_job(detail="execution")` for the exact prompt, request evidence and compact execution instructions, or `detail="full"` for complete diagnostics. Project `detail="full"` and portable exports retain complete history. Poll summary state rather than refetching full payloads.

Recipe, sequence and source catalogs default to summaries and accept ID, stage/role where relevant, pagination, detail and provenance controls. Full bibliographies and shared production context are available using `get_context(context_id, version)` from the immutable hash-addressed references in the claim. Cached context is evidence, never permission: current policy and contract are rechecked before new provider execution.

Packets above 64 KiB fail before a new job is committed with `payload_too_large`, field byte sizes and targeted fetch/scope remedies. Required content is never truncated. Run `python benchmark_handoffs.py` from backend for offline minified UTF-8 measurements; exact token counts require an explicitly named installed tokenizer (`--tokenizer`). Bytes are not billed tokens.
