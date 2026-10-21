# Studio MCP Implementation Plan

> **For agentic workers:** Use executing-plans to implement this plan task-by-task. Track evidence below. No Git repository exists; Git-only helpers and commits are inapplicable.

**Goal:** Deliver a real shared studio UI/MCP workflow with agent generation handoffs, asset returns, per-step approval policy, and configurable JSON API generators.
**Architecture:** Additive Python studio service backed by its own SQLite DB and project media, a loopback FastAPI app, and a stdio MCP proxy. The Next.js `/studio` screen uses a same-origin server proxy to the same service. Preserve legacy code/data.
**Tech Stack:** existing Python/SQLite/FastAPI/httpx/Pillow, official MCP SDK, existing Next.js/React/CSS.
**Spec:** ../specs/2026-10-21-studio-mcp-design.md (user clarification overrides previous defaults).

## Global constraints
- No fabricated generation, no automatic Google Flow login, no changes to existing studio.db or user media.
- Per-step approval policy is set by the user in UI; automatic progression is visibly distinct from human approval.
- MCP and browser share saved state, revisions, jobs and take association.
- Agent-generated assets return by exact project/shot/job ID, preserve previous takes, and validate actual media.
- Provider keys stay on backend; the JSON connector contract is explicit.

## Review focus
- Late or duplicate result after prompts change must not advance the wrong revision.
- Approval policy switched on after auto progression must block current/future completion until reviewed.
- Two agents claiming the same next task must not create duplicate work.
- Out-of-root file import and wrong media content must fail without mutating the project.
- Provider unreachable or malformed result must become a useful failed job with no false asset.

## Task 1 — Shared workflow and returned assets
Files: backend/studio/{store.py,workflow.py,assets.py,templates.py}, backend/tests/test_studio.py.
Interface: StudioStore(path,media_root,inbox); create/list/get/update project with optimistic revisions; next_action; claim_handoff; return_result; review; set_policy. JSON snapshots include revision, steps, shots, jobs, assets, history.
- [x] Write behavior tests for manual and automatic gates, duplicate claim/return, stale return, project isolation and invalid imports; run RED.
- [x] Implement SQLite transactions, immutable handoff snapshot, output validation, explicit review and progression.
- [x] Run `python -m unittest discover -s tests -v`; 23 tests pass, including MP4 and local API fixture checks.

## Task 2 — API, MCP and generator connection
Files: backend/studio/{api.py,providers.py}, backend/studio_mcp.py, backend/requirements-studio.txt, configs/, docs/MCP.md, launch-studio.ps1.
Interface: authenticated loopback /studio/v1 endpoints; SDK tools proxy those operations. JSON API adapter POSTs handoff and accepts synchronous base64 output or asynchronous job ID with polling; no arbitrary output URL downloads.
- [x] Write API/connector tests for unauthorized policy change, provider response validation and late failure; run RED. Unavailable bridge returns an explicit connection error.
- [x] Implement routes/adapter/MCP and configuration examples. Ruling: optional bearer key entered by user is stored only in the ignored local backend configuration, never sent back to UI/MCP; no provider selected or paid call made.
- [x] Run suite and real SDK stdio handshake/tool calls against isolated live API: shared state, generator ZIP export and duplication passed.

## Task 3 — Connected studio UI and delivery
Files: frontend/src/app/studio/{page.tsx,studio.css}, frontend/src/app/api/studio/[...path]/route.ts, tests/browser-studio.cjs.
Interface: same-origin API proxy with browser credential; actual studio page renders service state and human policy/review controls. Poll while visible and refetch after mutations; explicit revision errors.
- [x] Initial browser route unavailable; subsequent browser checks found proxy origin and cached-component config errors, repaired from observed diagnostics.
- [x] Implement orange/glass project/template workspace, workflow, creative/shot forms, job/assets/review, per-step toggles, provider and MCP setup; generator selection/ZIP, duplicate and Trash added per user request.
- [x] TypeScript and production Next build pass. Browser verifies shared MCP records, real thumbnail, download, duplicate/delete/restore, policy persistence, independent drafts, stale review protection and no home overflow at 1280/1024/375/320.
- [x] Independent review found two workflow issues; both repaired with failing-then-passing regressions, and reviewer confirmed fixes. Production app running and verified at port 3000 with separate real data; attempted user-tab replacement blocked by browser security, provide link instead.

## Execution ledger
- Expanded by user: generator-specific portable ZIP handoff for non-API use, generator/template selection, duplicate project, and recoverable Delete/Trash/Restore. Added tests before implementation.
- Core and API verification: 21 isolated behavior tests pass. Live SDK stdio bridge roundtrip passed before latest additions; rerun after all changes.
- Review repairs: bind text document decisions to displayed revision; recheck closed jobs inside return transaction; preserve succeeded provider jobs after late failures; rejection clears active motion takes; separate settings/shot draft flags.
- Final evidence: 23 backend tests pass; Next production build succeeds; real stdio SDK tool calls cover handoff/return, second-client persistence, export and duplication; browser end-to-end flow passes. No real image/video provider or all four installed agent clients are claimed as connected. Configuration examples and setup instructions provided.
- Final runtime: launch-studio.ps1 starts hidden loopback API 8010 and production Next server 3000 when a build exists. Real workspace starts empty; prototype browser projects remain separate. QA fixtures only in .studio-test and output/playwright.
- Deferred limitation: API connection implements documented JSON Job API; vendor-specific adapters and automatic Flow account control remain separate work. No cloud media hosting or built-in video editor added.
- User's clarification supplies the intended operational loop and authorizes the implementation; execute inline to preserve momentum.
- No Git: preserve original files; use additive paths and test-only DB/media. Do not initialize a repo or run Git-dependent skill helpers.
- Preflight: task 2 consumes task 1 JSON snapshots; task 3 consumes task 2 REST API. Same model across all paths. Provider adapter configured by user; no paid calls in verification.
- Visual thesis: dark orange frosted glass, quiet typography, a clear next action and tangible real media.
- Content plan: project navigation -> current stage and next action -> shots/review -> connections.
- Interaction thesis: fast panel transitions, clear pending/saved feedback, and visible progression when returned media completes a step.
