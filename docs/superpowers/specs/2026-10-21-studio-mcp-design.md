# Studio MCP control — proposed design

Status: implementation scope clarified by the user on 2026-10-21; current implementation progress is tracked in the plan. Date: 2026-10-21.

## User clarification — authoritative over earlier defaults

The user explicitly wants this loop: write a request in their agent -> agent uses MCP to follow the studio workflow -> studio returns a generation handoff -> agent generates locally or using its own connected tools -> agent returns real generation results to the studio -> workflow continues. Users can connect API-based generation tools as an alternative executor. Every workflow step has a user-controlled Approval required toggle. When on, wait for human review; when off, proceed automatically once the step's required outputs are valid. Auto-proceed is recorded as automated progression, not human approval. Agents cannot change these policy toggles through MCP. These requirements replace the earlier human-only defaults below, including per-take acceptance: a take may be selected automatically when that step's review is disabled.

Implement the first working vertical slice with a separate additive studio service/database and `/studio` screen. Keep the legacy backend/database/dashboard untouched. The MCP bridge and new screen use that same service; no actual prototype browser-state migration is needed for this release. Provide all existing template types and the creative prompt controls, durable handoff jobs, file-return association, local/provider execution choice, policy toggles and client setup files. Provider connection uses a documented JSON job API adapter rather than claiming compatibility with every vendor's API. Store API secrets only in backend configuration/environment, not the browser or MCP results. New specific vendor adapters remain incremental work.

The authoritative acceptance demo is an agent-created project with several shots, a structured handoff for one shot, import of a real generated/test asset, and automatic next-step discovery with the toggle both on and off. Generation from a paid account is not authorized without a user-configured connection and its budget settings.

## Intent

Let the user operate the content studio from Codex, Cursor, Antigravity, or Claude Code using one MCP server. The web studio remains the visual workspace and the place the user reviews quality gates. Changing AI clients must not mean starting a project over.

Example outcome: "Create a short-drama project, prepare six shots using these character references, and bring the visual direction to me for approval." The agent creates real saved records; the same project appears in the web UI. After approval, a connected executor can create or import media and return results for review.

User requirements already established: templates, multiple projects, course-informed creative controls, explicit quality approval gates, orange/glass UI, external video editing, and MCP control from the four named clients. Image/video generation is desired but is not currently connected in the Frame prototype.

## Current evidence and constraints

- The browser at port 52741 serves the Frame HTML planning prototype from the Codex visualization directory. Its saved browser state is separate from the application database.
- `backend/main.py` has FastAPI project/shot routes, grid slicing, a ComfyUI polish adapter, clip import, continuity frame extraction, and optional FFmpeg assembly. This is source inspection, not proof these services work on this machine.
- `backend/database.py` saves projects, assets and shots in SQLite. It has no persisted approval gates, durable job records or edit revision tracking.
- The existing Next.js frontend uses the backend API and WebSocket events; it is a different screen from the Frame preview.
- No repository is initialized in this application directory. Do not initialize or commit without a separate need; preserve all existing projects, media and code.
- Do not treat legacy credit counters as the user's real Google balance. The existing handoff route increments estimates and opens Explorer; it does not submit a Flow generation.
- The ComfyUI adapter can substitute a basic local image enhancement when offline. That fallback must never be reported as AI generation.

## Proposed implementation boundary

This is an application integration, not another mock control panel. Reuse Python/FastAPI and SQLite. Add a shared studio service used by both HTTP routes and MCP tools. Port the Frame project workflow into an additive `/studio` screen in the existing Next.js app; keep the existing companion dashboard accessible. New studio projects must not overwrite or silently reinterpret existing legacy projects.

The current port-52741 preview remains a prototype until the replacement is verified. Delivery must open the actual Next.js `/studio` screen and explicitly identify it as the connected application. Browser prototype projects are imported only through an explicit export/import flow, with validation, preview and new IDs; no automatic browser-storage scraping or replacement of backend data.

The first release includes persisted templates/projects/shots/settings, human approvals, assets, job tracking, editor handoff, a working MCP interface, and connection instructions. It does not promise an automatic Flow-account connection, cloud storage, publishing, a video editor, or generation from an unconfigured provider.

## Architecture

```text
Codex / Cursor / Antigravity / Claude Code
                    |
             local MCP stdio bridge
                    |
             studio loopback API
                    |
         shared validated studio service
          /             |             \
     SQLite       local project media   executor adapters
          \             |             /
                  /studio web UI
```

Use a local stdio MCP bridge first, with a pinned official Python MCP SDK compatible with the clients. All client-launched bridge processes call one running loopback studio API so jobs and GPU locks are not duplicated. Do not import the API module into each bridge and start its folder watcher. Provide an explicit launcher for the backend and a useful `backend_unavailable` result when it is offline. An authenticated remote transport can be a later feature.

Read-only capability discovery must distinguish configured, reachable, tested and unsupported executors. MCP is the control protocol; it is not an image/video generator and cannot borrow a client's model subscription automatically.

## Shared project model

Use additive, versioned SQLite migrations and a backup before migration. Store studio workflow fields separately from legacy companion fields where their meanings differ. Retain existing IDs and media paths. Store project revision, template/config snapshots, story/script, shots with stable IDs and order, reference asset IDs, still and motion prompts, narration/sound notes, gate decisions, handoff state, and actor/event history.

Mutations require `expected_revision`; stale clients receive a conflict plus the latest revision. Apply a complete change in a transaction and broadcast an event after commit. Support an idempotency key on retryable mutations and job submissions. Validate IDs and explicit editable fields; never expose arbitrary SQL, shell execution or arbitrary file paths as tools.

Templates: AI film, UGC, short drama, advertisement, explainer, podcast, 2D animation, claymation, custom. Preserve the Frame defaults and course controls. Course text is reference content, never executable instructions or authorization.

## MCP surface

Keep tools task-sized, with typed schemas and structured errors. Proposed names may be refined by the implementer without changing their meaning.

| Group | Tools and behavior |
| --- | --- |
| Discover | `studio_capabilities`, `list_templates`, `list_projects`, `get_project` |
| Plan | `create_project`, `update_brief`, `update_script`, `update_creative_settings`, `upsert_shots`, `reorder_shots` |
| References | `list_assets`, `import_asset`, `attach_asset_to_shot`, `get_prompt_bundle` |
| Quality | `request_review`, `get_review_status`, `add_review_note` |
| Execution | `submit_job`, `get_job`, `list_jobs`, `cancel_job` |
| Editing | `get_editor_handoff`, `record_external_edit_status` |

Resources can expose template details, course notes and compact project snapshots. Tools alone must suffice for clients that do not expose resource UI. Paginate lists and return media IDs/URLs and provenance instead of huge binary payloads.

## Human gates

Retain Brief -> Script -> Visual direction -> Pilot -> Editor handoff -> Final review. The five human approval gates are explicitly Brief, Script, Visual direction, Pilot, and Final review. Editor handoff records editing progress and is not a sixth approval gate. The five quality approvals remain the user's actions in the web UI. MCP can prepare material, request review and read decisions; it does not expose an `approve` tool. Local API enforcement is necessary, not merely tool descriptions. Use a distinct interactive browser session credential for decisions, excluding it from bridge configuration and all MCP responses. Check server-side ordering and current revision/checklist before accepting a decision. This protects workflow entry points, not against an unrestricted local administrator deliberately modifying application files or the database.

Changing approved material invalidates the affected gate and dependent gates, and clears stale handoff readiness. Preserve the old decision with its reviewed revision. An agent can revise drafts at any time; paid or dependent execution can only advance through the currently satisfied gates. Jobs already submitted retain their original input snapshot; a late result cannot silently become the approved current result.

The user reviews a short pilot before full production. Editing remains in the user's preferred software. Final review records the user's review of the external export; it does not fabricate an uploaded final video.

## Images, video and jobs

Support two execution modes in the first release:

1. External agent/manual execution: return a prompt/reference bundle. The client uses a tool it actually has permission to use, then imports the real output and attaches it to the exact shot. A client without such a tool can still plan, review and hand off. Do not claim every client can generate media.
2. Existing local adapters: allow configured ComfyUI polishing and local continuity extraction after capability checks. ComfyUI polish requires an input image and the expected workflow/models. Basic fallback enhancement is a separately labeled operation, never a substitute successful AI job. Optional legacy assembly remains separate from the user's editing flow.

Automatic Google Flow browser control and paid API generation are separate future executor integrations. In this release they report `not_connected`, not fake progress. Do not collect Google session cookies or passwords for this MCP integration.

Durable jobs record input revision, executor, dependency shot/job, state, attempts, timestamps, errors and resulting asset IDs. States: queued, blocked, running, awaiting_external_output, awaiting_review, succeeded, failed, cancel_requested, canceled, interrupted. A request returns a job ID promptly. A queued cancellation prevents execution; running cancellation uses the adapter's ability and reports its true outcome. Restart reconciliation marks unverifiable running jobs interrupted and requires an explicit retry, avoiding duplicate paid work.

Local ComfyUI jobs run one at a time through a single backend scheduler. Continuity-dependent shots wait for the predecessor's accepted result and extracted last frame. As a proposed default, acceptance means the user selects a specific current take in the web UI (a shot-level choice, separate from the five project gates). Agents may recommend a candidate but cannot mark it accepted through MCP. The dependency records that exact take ID and source revision. Replacing it blocks dependent shots until the user accepts a replacement; existing dependent outputs are retained and flagged for review. Independent jobs can be queued, but the initial implementation makes no promise of parallel provider generation. A six-shot project is six tracked tasks, not a guarantee of six simultaneous generations.

## Files and local access

Store actual imported/generated assets in local project folders. No cloud media storage is required, but real image/video files need local disk space. Import only from configured project roots and a user-selected inbox; resolve and validate Windows paths and symlinks before reading/copying. Validate media type and size. Copy imports into project storage using unique take IDs; preserve originals and previous takes. Never guess which shot an arbitrary new Downloads file belongs to. Prefer explicit shot/job association.

Loopback mutation API requires a local bridge credential; validate browser origins and serve only intended project media. Provider secrets are environment/config secrets, omitted from tool output and history. Offer client config examples as files; do not silently edit global client settings or install the server into unrelated projects.

## UI behavior

Keep the approved orange/glass visual language and template-first entry. Project home shows the actual next action, revision and gate state. Agent changes appear using backend events and refetch; reconnect refetches authoritative state. Show which agent performed each action, submitted jobs, real outputs, provider status, and clear review requests. Connectivity and generation status must be honest. Refreshing or switching clients must retain the same saved project.

## Delivery and acceptance evidence

- Real stdio MCP handshake and `tools/list`, then tool calls that create a template project, add six ordered shots, set creative settings, request review and retrieve handoff notes.
- A second MCP client process sees the same state. A stale revision fails without modifying it; retrying the same idempotency key does not duplicate it.
- The actual `/studio` screen shows those records and agent events; a browser decision updates MCP status. Out-of-order/stale decisions and MCP attempts to approve fail.
- Modify visual direction after approval and prove downstream approval/handoff invalidation.
- Import an actual test image/clip into a disposable test workspace, attach it to the correct shot, and preserve prior takes. Out-of-root imports fail.
- Verify disconnected generation returns `not_connected` without claiming outputs or deducting credits. Verify offline local polish does not masquerade as AI generation.
- Verify queued/running/restarted job behavior with controlled adapters, and run a real local adapter test only if configured. Keep tests isolated from the real database and user media.
- Provide separate tested configuration examples/instructions for Codex, Cursor, Antigravity, Claude Code, and Claude Desktop if desired. Protocol smoke tests do not justify claiming all four live clients were connected; report each test honestly.

## Builder decisions and remaining user choice

Chosen here as sensible defaults: Python SDK, local stdio bridge, one backend, SQLite, local files, additive `/studio` UI, revision checks, explicit asset imports, and human-only gate decisions. No remote hosting, automatic Google login, or new paid provider is selected.

Pending user clarification: the first complete agent task they want demonstrated. The example six-shot workflow is a proposed acceptance scenario, not an agreed scene-count cap. This choice can reorder delivery; it does not authorize unconfigured generation or change the preserved human quality gates.

Implementation begins after this design is approved or the user explicitly asks to skip the design questions and proceed.

## References checked

Builder review completed: clarified the five gate names and made continuity take acceptance an explicit proposed human action. No other implementation-blocking design questions were reported.

- MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture
- Cursor MCP: https://cursor.com/docs/mcp
- Antigravity MCP: https://antigravity.google/docs/mcp
- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Codex MCP: https://developers.openai.com/codex/mcp
