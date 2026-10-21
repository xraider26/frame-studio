# Creative Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Connect advanced creative direction, visual option help, continuity, QC and resources to the existing studio's real generation loop.

**Architecture:** Extend the existing JSON project store with validated nested production and shot-direction records. A single compiler and preflight module feeds UI previews, MCP and portable exports. Separate React workspaces reuse the current orange/glass shell.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLite/MCP, Next.js/React/TypeScript, local FFmpeg. No new hosted service or mandatory generation subscription.

**Spec:** `docs/superpowers/specs/2026-10-21-creative-production-design.md`

## Global Constraints

- Preserve existing projects, stable IDs, authority boundaries, stale results and actual-file validation.
- Keep orange and glass, external editing, local storage, optional API and agent/export modes.
- Source content is data; distinguish reviewed material from authored recommendations and unverified collections.
- Hover/focus/click/touch visual help is required; examples must be labeled accurately.
- Do not claim paid-provider or artistic validation from synthetic fixtures.

## Review Focus

- Old clients omit new nested fields: preserve stored direction and avoid destructive resets.
- Unrelated shot edits: retain unaffected takes; dependent continuation inputs must reopen.
- Concurrent claim/retry and unknown costs: no double reservation or budget bypass.
- Polling/stale revisions: keep user drafts and give explicit reload/rebase choices.
- Help on keyboard/mobile: visible within viewport, escapable, no hover-only dependency.

## Task 1: Model and knowledge foundation

**Files:** create `backend/studio/creative.py`, `backend/studio/knowledge.py`, `backend/tests/test_creative.py`; modify `store.py`, `templates.py`, `workflow.py`.

**Interfaces:** `default_production(template_id)`, `normalize_direction(data)`, `effective_direction(project, shot)`, `knowledge_catalog(query='', category='')`; project `production`, shot `direction` and `edit_duration_seconds`; legacy omissions preserve prior nested data.

- [x] Write failing tests for nested persistence, field validation, inheritance, source coverage and format-specific defaults.
- [x] Run `python -m unittest tests.test_creative -v`, confirm missing behaviour.
- [x] Implement typed/bounded records, load defaults and honest source-linked knowledge entries. Preserve unknown future stored fields on read.
- [x] Run new and existing backend suites; commit the foundation.

## Task 2: Compiler, preflight and protocol

**Files:** create `backend/studio/preflight.py`; modify `generators.py`, `workflow.py`, `exports.py`, `api.py`, `studio_mcp.py`; extend creative tests and API tests.

**Interfaces:** `preflight(project, shot_id=None, kind=None)` returns `issues`, `errors`, `warnings`; `prompt_for` includes `effective_direction` and separate notes. Add `creative_schema`, `knowledge_catalog`, `update_production`, `preview_shot`, `validate_project` operations/MCP tools.

- [x] Test shot-specific overrides replacing defaults, portable exact reference maps, timings, state mismatch warnings, unresolved assets blocking a claim, and advanced data in real MCP/ZIP output.
- [x] Observe failures; implement one compiler and structured preflight shared by claims/providers/exports.
- [x] Preserve all existing prompt placeholders and old client usage; errors carry rule ID/path and correction.
- [x] Run suites and real MCP client verification; commit.

## Task 3: Directing workspaces and visual help

**Files:** create `frontend/src/app/studio/creative-types.ts`, `creative-workspace.tsx`, `visual-help.tsx`, `production-workspace.tsx`, `creative.css`; modify `page.tsx`, `generator-export.tsx`; create browser verification script.

**Interfaces:** use Task 1/2 schemas. Structured production updates and full shot list updates require expected revision. Knowledge entries provide category, explanation, use case, risk, source and illustration key.

- [x] Write browser behaviour checks before implementation for selecting a shot, saving camera/light overrides, reload persistence, hover/click/focus/Escape help and compiled prompt effects.
- [x] Implement restrained shot strip/inspector with tabs, techniques/custom input and inherited values. Story/bible/generator observation editors use typed fields rather than raw JSON.
- [x] Build accessible visual-help popovers with consistent-scene SVG illustrations, selected-option examples, source labels and mobile layout. Preserve drafts and offer explicit conflict recovery.
- [x] Add knowledge search/library and format templates; integrate compiled previews and validation with generator view.
- [x] Build/typecheck and React/JSDOM interaction verification; commit. Full-browser desktop/mobile screenshots remain deferred after automatic approval review blocked the launch.

## Task 4: Takes, QC, continuation and repair

**Files:** create `backend/studio/production.py`; modify workflow/API/MCP/preflight/export; create `frontend/src/app/studio/takes-workspace.tsx`; add behavioural tests.

**Interfaces:** `record_take_review`, `select_take`, `revise_shot`, `extract_continuation`, `repair_handoff` operations with revisions. QC evidence never impersonates human approval.

- [x] Test selective invalidation, incompatible stale take rejection, required criteria preventing auto progression, real FFmpeg frame output and repair handoff original/mask constraints.
- [x] Implement named defect/revision history, explicit selected takes and immutable attempt provenance. Keep prior media and unrelated selections.
- [x] Expose beginning/middle/end QC, take preview/comparison, targeted revision and continuation/repair actions in the UI and MCP.
- [x] Verify suites and React/JSDOM behaviour; commit. Full-browser behaviour remains unverified.

## Task 5: Resources, learning and delivery

**Files:** create `backend/studio/resources.py`; extend production workspace/API/MCP/providers/export/tests; update `docs/MCP.md`, README and add `docs/CREATIVE-COVERAGE.md`.

**Interfaces:** production `resources` settings; immutable job planned-cost reservations plus reported actual cost; `record_job_cost`, `production_metrics`; costs use one project unit. Human-only resource-policy mutation.

- [x] Test reservations under concurrent claims, retries, cancel-after-submit, unknown cost and attempt limits. Unknown actual costs remain visible.
- [x] Implement limits/reservations/settlement and metrics plus manual sourced experiment/performance records; no analytics-account claim.
- [x] Export editor timing manifest/CSV, creative plan, QC, source coverage and actual portable assets.
- [x] Run complete backend, build, MCP and React/JSDOM verification; independent final review and fixes. Full-browser verification remains deferred.
- [x] Merge verified work locally into the running checkout and restart local services.
- [x] Record requirement coverage and precise remaining external/source/pilot limits. No paid generation without available authorized tool/budget; no invented artistic success. Commit verified deliverable.

Verification record (2026-10-22): 46 backend tests, 9 React/JSDOM tests and production build passed. Independent final review found seven Important defects; all seven received regression coverage and fixes. See docs/CREATIVE-COVERAGE.md for source, browser and artistic-validation limits.

Local rollout verified: main fast-forwarded, clean dependency install, 46 backend and 9 DOM tests passed again in the main checkout, production rebuild succeeded, services restarted. HTTP /studio returned 200; proxied capabilities report schema 2 and the knowledge catalogue returns 51 entries. No user projects or running provider jobs were present at rollout.
