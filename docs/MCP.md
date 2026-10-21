# Frame Studio: agent-controlled workflow

## Creative production upgrade (schema v2)

The studio now shares structured story/bible/shot direction with its agents. See [feature and source coverage](CREATIVE-COVERAGE.md) for exact capabilities, tests and current limits.

- `creative_schema`: field definitions, validation and inheritance rules. Shot `direction` includes camera/composition, lighting, art, action/states, sound, exact references and quality criteria; `edit_duration_seconds` and `edit_in_seconds` are separate from generation duration.
- `knowledge_catalog(query, category)`: searchable technique explanations, visual keys, use cases, risks, source/provenance and editable `apply` patches. Coverage explicitly distinguishes the supplied playbook from unavailable original PDF catalogues.
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

From `G:/AI/YT/flow-companion-studio`, run `./launch-studio.ps1`. It starts the loopback workflow API on port 8010 and the Next.js frontend on port 3000 in hidden background processes. Logs are in the project directory. Run `./launch-studio.ps1 -BackendOnly` if the UI is already running. The legacy companion API on port 8000 is separate.

If dependencies need installing:

```powershell
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-studio.txt
```

Install frontend dependencies using its package lock if they are missing. FFmpeg/FFprobe must be in PATH to validate returned MP4 videos. No generation API key is required for planning or the agent handoff mode. A local or remote generation tool must be available separately to create real media.

## Connect your agent

All four clients run the same local stdio command. Use the exact executable and script in `configs/mcp-clients.json`; merge only the `frame_studio` entry into existing client settings. Do not replace other servers. Change paths if the project moves. No credential needs to be copied into client config: the bridge reads the local agent token created by the backend. Set `STUDIO_CLIENT_NAME` to identify the client in project activity.

- **Codex:** merge `configs/codex-config.toml` into the MCP configuration using Codex Settings → MCP servers, or its trusted-project/user `config.toml` workflow. Restart/reconnect and inspect available tools. See https://developers.openai.com/codex/mcp.
- **Cursor:** merge the JSON entry into workspace `.cursor/mcp.json` or add it through MCP settings. See https://cursor.com/docs/mcp.
- **Claude Code:** merge the JSON entry into project `.mcp.json`, or use `claude mcp add --transport stdio frame_studio -- G:/AI/YT/flow-companion-studio/backend/.venv/Scripts/python.exe G:/AI/YT/flow-companion-studio/backend/studio_mcp.py`. Review project trust when prompted. See https://code.claude.com/docs/en/mcp.
- **Antigravity:** add the JSON entry through Manage MCP Servers / raw configuration. The relevant setting differs between IDE, app and CLI; see https://antigravity.google/docs/mcp.
- **Claude Desktop:** use the same JSON server entry in its supported local MCP server configuration and restart it. This is a desktop server, not a public remote connector.

These are portable config examples. Verification of the MCP protocol and SDK bridge does not mean every installed client has already been configured. Existing client/global settings are not modified by this project.

## The agent loop

1. Call `studio_capabilities`, then create or open a project. `get_project` returns its saved revision, approval policy and next action.
2. Write the actual brief and script through `complete_step`. Set creative controls and the ordered shots. User-defined review steps return `await_approval`; stop there and let the user review in the studio.
3. When `next_action` is `generate`, call `claim_generation` with a unique request ID. Reuse it only when retrying that exact call. The result includes the immutable prompt/reference/settings snapshot, job ID and local return inbox.
4. If `already_claimed` is true, inspect the job; do not initiate a second paid generation. Resume an unfinished handoff only when you know the previous executor has stopped. Cancel a waiting handoff before explicitly retrying failed external work.
5. Use a generation tool the user has actually authorized and connected. Save the actual PNG/JPEG/WebP or MP4 into the returned `return_inbox`. Handoffs include local reference image paths; reading them requires the client's local file/tool access.
6. Call `return_generation(job_id, output_path)`. The studio validates the media, copies it into the project as a new take, records provenance and returns the next action. Duplicate returns do not create extra takes. Outputs for changed prompts are retained as stale and cannot complete the current revision.
7. Continue until a human approval is required, an actual external edit is needed, or the workflow finishes. After production, get `editor_handoff` for the ordered take paths and editing notes. Return the actual external edit with `import_final`.

Example request:

> Use Frame Studio to prepare a six-shot short drama about a traveler entering an abandoned observatory. Follow its workflow and review policy. When generation is available, get the handoff, generate using my connected local tool, return each output to the studio, and continue to the next permitted step.

The studio does not supply a generation model through MCP, borrow client subscriptions, or access Google Flow automatically. An agent without image/video tools can still plan, get prompts, import supplied outputs and track reviews.

## Approval controls

Every workflow step has an **Approval required** checkbox in Workflow & approvals. On means the studio waits for an explicit browser review. Off means valid outputs allow automatic progression, visibly recorded as `auto_proceeded`, never human approval. Agents cannot turn off review or approve through the MCP tools. Enabling review again reopens the current review and dependent steps. Changes to source material invalidate affected progression; old media and decisions remain in activity/history.

The workflow is Brief → Script → Visual direction → Pilot → Production → Editor handoff → Final review. Visual direction requires one real image per shot; pilot requires the first shot's video; production requires videos for the remaining shots. The three shots in templates are editable starting points, not a generation/concurrency limit. The current shot list supports 1–200 planned shots. Agent handoffs are sequential next-action tasks; provider parallelism is not promised.

## Export without generation APIs

Open **Generator handoff**, choose **External agent / export**, select the video and image prompt profiles, and apply the choices. **Prepare export package** creates a real ZIP; **Download handoff ZIP** saves it. You can give the file to your Flow agent or another generator agent.

Profiles currently include Google Flow/Veo, Runway image-to-video, Runway text-to-video, general/Runway image prompts and custom templates. They change actual prompt content, not just a label. Custom templates accept the documented simple placeholders. Generator capabilities and supported clip durations still depend on the selected model; a profile does not connect or authenticate an account.

The ZIP contains portable `manifest.json`, `prompts.md`, `README.txt` and available reference/keyframe images. It carries project/shot IDs, source revision, intended settings, output filenames and review policy. It is not native Flow/Runway project format and does not contain an automatically rendered video. The receiving agent should check live studio state, claim each permitted task and return actual files through MCP; offline-generated files can be returned when connected again. An exported snapshot cannot override later prompt changes or review requirements.

## Duplicate, delete and restore

The buttons under the project dropdown provide **Duplicate**, **Delete** and **Trash**. Duplicate copies the plan, documents, generator choices and reference images to new IDs. Generated takes, jobs and approval decisions start fresh, with approval enabled on each step. Delete is recoverable: the project goes to Trash and media stays on disk. Trash offers **Restore project**. The app does not expose permanent file deletion. Projects with an active API job must finish it before being moved to Trash.

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

In Template library, save a named snapshot of selected creative settings, workflow/quality gates, and/or story and shot plan. A successful shot can supply the reusable camera, lighting and art defaults. Notes record what worked. Use a saved template in the new-project picker or apply selected sections to the current project. Rename/delete manage library entries independently of existing projects. Templates live in the same local SQLite database and survive restarts and deletion of the source project.

MCP: `list_templates` includes built-in and saved IDs, `get_saved_template` reads saved snapshots, `create_project` accepts a saved ID, and `apply_project_template` accepts `settings` and/or `story` with both project and template revisions. Saving/renaming/deleting templates and applying workflow policy are human UI controls. Agent-created projects retain default approval/quality policy. Story application replaces shots and prepared documents, reconciling references into the replaced cast/shot plan; affected outputs reopen, original media is retained. Snapshots omit reference file bindings (reattach them), output takes, completed approvals, spending settings/history, observed capabilities and experiment results.

## Batch production and queue workers

See `docs/PRODUCTION-SCALE.md` for the full workflow and limits. MCP tools: `create_batch`, `production_queue`, `get_batch`, `claim_queue_task`, `renew_queue_task`, `finish_queue_task`, and `recipe_metrics`. `create_batch` queues actual independent planning projects from an idea; it does not invent completed scripts/media. Claim work with a unique stable request ID, refresh the project, execute its real next action, and renew a 15-minute lease during long work. Finish after meaningful recorded progress or block with a real reason. User approval waits must be respected. Queue policy, pause/priority, identity sync and recipe endorsements are human controls in the UI. Batch caps also govern direct generation/provider starts.
