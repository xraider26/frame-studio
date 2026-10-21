# Production Scale Implementation Plan

> Execute independent domains with dispatching-parallel-agents and TDD; integrate and request one final review.

**Goal:** Turn an idea into a durable batch production workload for connected agents, with canonical identity, bounded defect retries, queue visibility, recipe evidence and Basic/Professional controls.

**Spec:** docs/superpowers/specs/2026-10-22-production-scale-design.md

**Architecture:** Extend existing projects/SQLite transactions and MCP contracts. Separate batch/dispatch, identity and recipe modules; focused React queue/mode components. Keep real-file validation and existing compiler/review/resource gates. No new dependencies.

## Constraints and review focus

- Source ideas are planning inputs; agents supply real planning and generated outputs. No fake completion or fabricated AI inspection.
- Batch creation and dispatch claims are atomic/idempotent. Leases expire/recover. Pause and caps cover direct generation and API provider starts as well as queued work.
- Unknown exposure blocks configured hard caps; concurrency and retries remain bounded. Existing user-only policies cannot be bypassed by agent batch/template operations.
- Canonical real files/definitions propagate with revisions; dependency changes invalidate actual inputs and preserve unrelated files.
- Mode changes are presentation-only and retain drafts, errors, QC/reference access and budgets.
- Recipe evidence requires actual inspected compatible takes, human attribution and matching recipe inputs; historical evidence is clearly scoped.

## Independent task A — Basic/Professional controls

**Own:** new frontend control-mode.tsx/control-mode.css, creative-workspace.tsx, production-workspace.tsx, project-direction.tsx, generator-export.tsx, dedicated mode DOM tests. Keep page/store/API files untouched.

- [x] Write failing persistence/no-hidden-draft-loss tests.
- [x] Add persisted per-workspace mode switches. Reduce optional direction details in Basic; retain essential inputs/help/references/errors/quality/budgets. Expose all current fields in Professional.
- [x] DOM tests, typecheck/lint; report files and results. No browser launch.

## Independent task B — Proven recipes

**Own:** saved_templates.py, new recipe_evidence.py, template-workspace.tsx, new recipe-evidence UI, dedicated backend/DOM tests. Root wires API/MCP as needed; do not edit workflow.py/store.py/page.tsx/api.py/studio_mcp.py.

- [x] RED tests for traceable source/copy usage, matching-input evidence, actual selected reviewed media, missing/defective/stale evidence rejection.
- [x] Add source/snapshot provenance and human pilot/production endorsement operation, source note, recorded assets and exact evidence level; never auto-label an untested template proven.
- [x] Add template recipe evidence/usage controls and UI; expose method `endorse_recipe(template_id, project_id, note, expected_revision, template_revision, level='pilot')` and `recipe_metrics(template_id)` for root API wiring. Policy is human-only.
- [x] Existing saved-template tests and dedicated tests pass; report interface details.

## Root task C — Batch engine, canonical identity and quality retries

**Own:** new batching.py/dispatch.py/identity.py, store.py/workflow.py/production.py/creative.py/providers.py/preflight.py, API/MCP, backend batch/identity/quality/SDK tests.

- [x] RED atomic bounded/idempotent batches, partial-failure rollback, leases/concurrent claims, pause/direct-claim enforcement, caps/unknown exposure and stale revisions.
- [x] Persist batches/task leases, factor project construction for atomic batch insertion, safe queue/task contexts and project dispatch policy. Implement claim/renew/finish leases with explicit progress and blocked reasons.
- [x] RED actual canonical file propagation/version changes, locked entity protection and scoped invalidation. Implement copying real canonical images, effective reference bindings and human synchronization.
- [x] RED selected inspected defect causes one bounded revision, repeat historical review cannot retrigger, exhaustion surfaces attention. Wire to existing resource/approval/compiler paths.
- [x] API/MCP tools with human policy boundary; actual SDK transport and existing suite green.

## Root task D — Idea launch and production queue UI

**Own:** new queue-workspace.tsx and tests/styles, page.tsx integration and shared type extensions if required. Do not edit task A/B owned files.

- [x] RED DOM tests for launch idea/count/template and explicit queue actions.
- [x] Idea launch, episodes/variations/campaign selection, optional briefs/identity source, priority/pause controls, batch limits and inspection-backed retry toggles. Queue shows real next action, worker leases, output waits, approvals, costs and failures; opens existing project workspaces.
- [x] Expose current identity source/version and human sync workflow; give agents a usable MCP queue instruction.
- [x] Integrate recipe endpoints and run full suites/builds.

## Final delivery

- [x] Independent whole-change review; reproduce/fix Important findings in one consolidated regression pass.
- [x] Requirement coverage and precise external/artistic/browser limits recorded.
- [ ] Merge locally after clean checks, build/restart existing app and verify real HTTP/API health. No GitHub push or paid generation inferred.

Verified before rollout: 81 backend tests, including actual MCP SDK queue transport, and 23 React/JSDOM tests passed; targeted new UI ESLint and webpack production build passed. Independent final review found two P2 defects; both were reproduced with RED tests and fixed: rejected-take retry consumption is recorded per asset, and deliberately excluded canonical references stay excluded through legacy fallback. Existing unrelated page lint debt remains scoped. Full-browser and paid/artistic validation remain unperformed.
