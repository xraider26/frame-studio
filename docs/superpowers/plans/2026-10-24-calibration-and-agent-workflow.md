# Orchestra Calibration and Agent Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ask for generators at first project use, establish a creator-approved visual baseline, trace course instructions through actual execution, and reduce handoff size without weakening workflow controls.

**Architecture:** Extend the existing Python workflow and human/agent API boundary rather than building a second orchestration engine. Store generator selection, calibration and execution evidence in versioned project/job records. Add compact response serializers separate from immutable stored jobs, with small React controls over the same server state.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLite/MCP backend, Next.js/React/TypeScript frontend and Electron Windows desktop; unittest and Node test runners. No generation provider or new framework is required.

**Spec:** [Calibration and connected-agent workflow design](../specs/2026-10-24-calibration-and-agent-workflow-design.md)

## Global Constraints

- Ask once per project; ask again when changed.
- A label is not evidence of an API connection or verified capabilities.
- Unknown versions are legitimate; unknown capabilities stay unknown.
- Existing projects retain their policies and are offered an explicit opt-in; old technical passes never become baseline approval.
- Agents cannot assert creator acceptance, change calibration mode or skip the gate.
- Keep stored v2 handoffs immutable and compact them only when serializing responses.
- Never truncate required policy/prompts/references to satisfy a budget.
- No new generation or alteration of the live calibration trial is part of implementation tests.
- Windows recovery must preserve credentials/data and retain allowed-root checks.

## Review Focus

1. Template or legacy model names may look complete without a creator selection: require source-aware confirmation for the new flow, preserve legacy execution policy until explicit adoption (Task 1).
2. Another session, queue worker or provider may bypass a UI-only calibration gate: enforce the same server decision at every new execution boundary (Task 2).
3. Changed or missing external execution metadata must not destroy already-owned output or silently count it as current (Task 3).
4. Compact retries/cached contracts may accidentally use stale policy or cause duplicate paid jobs: preserve request IDs, ownership and fresh contract checks (Task 4).
5. Packaged Windows launches may resolve a file and its parent to different physical roots: reject escapes while restoring valid imports (Task 5).

## Implementation sequence

Tasks are ordered for one implementer. Each includes its backend, UI, documentation and meaningful tests. Task 5 is a separately shippable reliability follow-up; it must not delay delivery of the generator/calibration protections. Do not rebuild or publish the installed app until the source changes have passed their checks and a packaged smoke test is explicitly scheduled.

All backend commands below run from `backend/` using that checkout's Python environment, for example `.venv/Scripts/python.exe -m unittest ...`. Node commands run from the indicated directory. Locate the actual local runtimes at execution time rather than hardcoding this test machine's Codex paths.

### Task 1: Generator questions at connected-agent entry

**Files**

- Create `backend/studio/generation_setup.py` and `backend/tests/test_generation_setup.py`.
- Modify `backend/studio/intake.py`, `workflow.py`, `agent_rules.py`, `store.py`, `api.py`, and `backend/studio_mcp.py`.
- Modify `frontend/src/app/studio/generator-settings.ts`, `generator-export.tsx`, `creative-types.ts`, `page.tsx`; create `generator-setup.tsx`.
- Add `frontend/tests/generator-setup.test.cjs` to `frontend/package.json` test scripts; update `docs/MCP.md` and `docs/GETTING-STARTED.md`.

**Interfaces**

- `generation_setup_state(project: dict | None, output_type: str | None = None) -> dict`: returns `status`, `questions`, saved selections and missing media kinds without mutating state.
- `validate_generation_setup(setup: dict, output_type: str) -> dict`: validates the version-1 shape defined in the spec; managed/unknown model versions accept `model=None`.
- `Studio.start_project_setup(project_id: str | None = None, output_type: str | None = None) -> dict` and `Studio.set_generation_setup(project_id: str, setup: dict, expected_revision: int, actor: str) -> dict` exposed through matching API/MCP operations.
- Include the setup fingerprint in `policy_snapshot`; synchronize old compiler setting fields from the new selections. Track image/video capability observations separately while preserving old data.

- [ ] Write failing tests: first bootstrap requests generator setup before creative questions; invoking with supplied creator choices does not ask twice; image-only asks no video question; managed built-in images need no invented model; deferred external video permits image calibration but blocks video execution; new sessions do not reopen unchanged setup; changing only video preserves image selection; template/legacy fields do not fabricate creator confirmation. Pin stale revision behavior.
- [ ] Run `python -m unittest discover -s tests -p test_generation_setup.py -v`; confirm failure for missing behavior.
- [ ] Implement read-only bootstrap, selection persistence and server gates. Permit setup saving/contract reads before setup completion; block creative preparation/claims in the new flow until relevant required selections are answered. Preserve legacy progression until explicit adoption. Advertise bootstrap in MCP initialization, `studio_capabilities`, tool descriptions and the UI entry point.
- [ ] Test UI rendering/serialization with `node --test tests/generator-setup.test.cjs` from `frontend/`: one grouped question, saved setup, built-in/external/connected distinction and no irrelevant video field. Exercise actual components/API requests, not only source-string searches.
- [ ] Run backend tests above plus `test_creative_intake.py` and `test_agent_contract.py`; run the frontend focused test. Update docs with the new loop and the limitation that the service cannot force arbitrary conversational behavior outside its tool boundary.
- [ ] Commit the independently working intake feature and its tests/docs.

### Task 2: One-image calibration with creator authority

**Files**

- Create `backend/studio/calibration.py`, `backend/tests/test_calibration.py`.
- Modify `backend/studio/workflow.py`, `production.py`, `store.py`, `api.py`, `agent_rules.py`, `dispatch.py`, `providers.py`; verify the ComfyUI execution entry uses the same gate.
- Create `frontend/src/app/studio/calibration-panel.tsx`, `frontend/tests/calibration.test.cjs`; modify `creative-types.ts`, `page.tsx` and frontend test scripts.

**Interfaces**

- `calibration_action(project: dict) -> dict | None`: decides representative-shot generation, `await_calibration_approval`, rejection repair or no additional gate.
- `style_contract_signature(project: dict) -> str`: pins shared style, continuity, scope, image-tool selection and style reference versions. `baseline_take_signature(project: dict, asset: dict) -> str` additionally pins the representative take/prompt. Adding new scene prompts under the unchanged shared contract must not revoke calibration; explicit style overrides require shot-specific acceptance.
- `Studio.review_calibration(project_id: str, asset_id: str, approve: bool, note: str, expected_revision: int, actor: str) -> dict`: human-only API, no agent acceptance tool.
- `Studio.set_calibration_mode(project_id: str, mode: str, expected_revision: int, actor: str) -> dict`: human-only opt-in/skip with history.
- Technical criteria accept versioned states `pass`, `fail`, `not_applicable`, `blocked`; a reason is required for the latter two. Normalize existing booleans on read without changing historical authorship or approval.

- [ ] Write failing tests: after the representative still returns and agent QC passes, a second image claim is blocked with `await_calibration_approval`; forged MCP approval/skip is forbidden; creator rejection preserves the asset and permits only representative repair; style/reference/image-tool changes revoke acceptance; adding a different world prompt preserves the shared baseline; explicit style overrides need shot-specific acceptance; video-only change preserves image acceptance; legacy QC does not become baseline approval; missing required canonical references cannot be waived with `not_applicable`; an environment-only scope with an actual style reference can establish the first baseline without asserting character likeness; queue/provider execution cannot bypass the gate. Cover stale approvals and two workers racing to claim.
- [ ] Run `python -m unittest discover -s tests -p test_calibration.py -v`; establish the failing cases.
- [ ] Implement the state machine in shared server decision functions. Initialize calibration only for new/adopted projects. Ensure `quality_passed` means technical evidence only; `await_calibration_approval` is a separate authority decision. Preserve existing step-level review policies and all previous takes.
- [ ] Add UI controls for choosing the representative shot, viewing its reference and take, accepting/rejecting with feedback, and explicitly skipping calibration. Clearly label agent review versus creator acceptance and show rejected attempts without deleting them.
- [ ] Run focused backend tests, `test_production.py`, `test_agent_contract.py` and `node --test tests/calibration.test.cjs` from `frontend/`. Verify an agent token gets HTTP 403 for both new human-only operations.
- [ ] Commit the calibration feature as a complete server/UI change.

### Task 3: Trace bootcamp rules and the actual generator prompt

**Files**

- Create `backend/studio/execution_evidence.py`, `backend/tests/test_execution_evidence.py`.
- Modify `backend/studio/recipes.py`, `generators.py`, `image_prompts.py`, `workflow.py`, `production.py`, `preflight.py`, `providers.py`, `api.py`, and `backend/studio_mcp.py`; route ComfyUI dispatch through the same evidence recorder.
- Create `frontend/src/app/studio/execution-evidence.tsx`, `frontend/tests/execution-evidence.test.cjs`; update types, page and test scripts.
- Update `docs/COURSE-RECIPES.md`, `docs/COURSE-SOURCES.md` and `docs/MCP.md`.

**Interfaces**

- `build_rule_application(project: dict, shot: dict, kind: str, stage: str) -> list[dict]`: rule/source/version/locator, requiredness, phase and applicability predicate result plus concrete prompt/reference/review/edit binding and applicability status/reason. Required applicable pre-generation rules need `applied` bindings; unverified prerequisites block; required media outcomes remain pending until actual review; external-edit rules gate only the relevant delivery stage.
- Extend recipe metadata with `required`, `stage`, `role_ids`, `phase` and declarative predicates. Add creator-confirmed `reference_requirements` scope to project data/types. Only human controls can narrow a required identity/product scope; optional irrelevant purposes may become not-applicable through their predicate result, never an arbitrary agent waiver.
- `validate_execution(job: dict, execution: dict) -> dict`: compares normalized line endings only; returns prompt/reference match state and evidence source, never semantic equivalence claims.
- `Studio.record_generation_execution(job_id: str, execution: dict, expected_revision: int, actor: str) -> dict`: owner-bound, revision-checked API/MCP evidence recording.
- Server-run provider adapters persist evidence automatically. External reported metadata is labeled `agent_reported`. Existing owned output is retained even if evidence is absent or mismatched, but cannot satisfy the current accepted baseline until resolved.

- [ ] Add failing tests for a missing required rule mapping; required pre-generation `unverified` blocking; optional unverified disclosure; predicate-backed versus forged not-applicable; media-outcome checks pending until inspection; phase-specific external-edit rules; original-page versus review-derived/studio-correction attribution; deduplicated environment/entity contributions; exact text/custom-template syntax preservation; compiler/submitted prompt differences; line-ending equivalence; reference version mismatch; forged evidence ownership; stale return retention; and legacy v2 jobs without newly mandatory metadata. Pin `needs_review` behavior rather than dropping a real file.
- [ ] Run `python -m unittest discover -s tests -p test_execution_evidence.py -v` and confirm failures.
- [ ] Implement prompt field precedence and trace records. Keep administrative notes outside visual prose. When material submitted content changes, require revised inputs/new claim and calibration decisions instead of silently rewriting the immutable handoff. Retain legacy job evidence as unavailable, not invented.
- [ ] Add a per-take view showing applicable source rules and scope, compiled/submitted prompts, differences, actual references, evidence source and unresolved checks. Avoid a blanket “bootcamp compliant” badge; display which rules were mapped and actually inspected.
- [ ] Run focused tests plus `test_course_recipes.py`, `test_recipe_evidence.py`, relevant image-prompt tests discovered at execution, and `node --test tests/execution-evidence.test.cjs`. Confirm no provider request occurs before required execution gates.
- [ ] Commit the complete traceability feature.

### Task 4: Compact versioned handoffs and targeted context reads

**Files**

- Create `backend/studio/handoffs.py`, `backend/tests/test_handoff_payloads.py`, and a scrubbed representative fixture under `backend/tests/fixtures/handoff-v3.json`.
- Modify `backend/studio/workflow.py`, `recipes.py`, `agent_rules.py`, `api.py`, `exports.py`, and `backend/studio_mcp.py`.
- Update consuming frontend types/requests, `docs/MCP.md` and `docs/NEXT-BETA-HANDOVER.md`.

**Interfaces**

- `serialize_claim(result: dict, response_format: str = 'compact') -> dict` emits schema v3 with one top-level handoff and no `job.handoff`; legacy format remains explicit.
- `build_execution_packet(project: dict, shot: dict, kind: str, stage: str, contract: dict) -> dict` consumes Tasks 1–3 and includes all applicable policy, source-rule, reference, execution and return requirements.
- `serialize_job(job: dict, detail: str = 'summary') -> dict`; `serialize_project(project: dict, detail: str = 'summary') -> dict` avoid recursively returning stored handoffs on polling. Full diagnostic reads remain available.
- Extend `recipe_catalog(recipe_id=None, stage=None, role=None, detail='summary', include_provenance=False, offset=0, limit=20)` and add equivalent sequence/source summary/detail controls. Add `get_context(context_id: str, version: str) -> dict` for immutable hash-addressed shared context.

- [ ] Write failing tests that the representative packet is at most `12 * 1024` minified UTF-8 bytes and bootstrap at most `16 * 1024`; no nested duplicate handoff/full coverage/unrelated roles appear; all execution-critical rules, owner, contract/revision, unknown-cost flags, paths and reference versions remain. Test explicit legacy format, stable hashes, original stored-v2 immutability, idempotent compact retries, changed policy and contract refresh, and old clients' documented top-level access pattern.
- [ ] Add a general `64 * 1024` byte ceiling test: an oversized legitimate packet gets `payload_too_large` before generation, identifies field sizes, preserves full data and gives targeted fetch/scope remedies; no required field is silently truncated. Add adversarial tests where compaction would otherwise omit a blocking policy or applicable rule.
- [ ] Run `python -m unittest discover -s tests -p test_handoff_payloads.py -v` and establish failures.
- [ ] Implement serializer-only compaction and targeted reads. Keep stored immutable evidence and portable export completeness. Validate cached contract/version references against current server state on every new claim/provider execution.
- [ ] Add an offline size benchmark that records byte counts and, when a declared tokenizer is available, exact token counts separately. Use scrubbed fixtures, not live credentials, local user paths or private course PDFs. Report measured savings without assuming bytes equal tokens.
- [ ] Run focused tests plus `test_agent_contract.py`, `test_studio_api.py`, exports and provider tests. Document schema-v3 shape change and legacy opt-in. Confirm frontend polling and generation-package consumers use the new access pattern.
- [ ] Commit the compact transport feature and benchmark.

### Task 5: Stable Windows data roots and coherent recovery

**Files**

- Modify `backend/studio/paths.py`, `assets.py`, `api.py`, `backend/studio_mcp.py`, desktop service/bridge entry discovered at execution, `desktop/runtime.cjs` and `desktop/main.cjs`.
- Extend `backend/tests/test_desktop_runtime.py`, create `backend/tests/test_physical_data_paths.py`, extend `desktop/tests/runtime.test.cjs`; update `docs/WINDOWS.md`.

**Interfaces**

- `resolve_writable_root(path: Path) -> Path`: resolve a stable physical writable directory using a sentinel/probe and verify directory/file resolution agree; remove the probe safely. Honor explicit overrides, report divergence, and do not merge/move competing databases automatically.
- Reuse this root consistently for DB, credentials, inbox, media, upload temporary files and exported MCP configuration. Keep `checked_file` containment after physical resolution.
- Atomic runtime publication contains ready service instance, PID, root and URL; cleanup only removes its own record. Recovery only controls children owned by the desktop instance.

- [ ] Write failing deterministic tests simulating logical-directory/physical-file divergence; valid imports succeed under one explicit physical root, while sibling prefixes, traversal, symlinks/junction escapes, stale discovery and another instance's PID remain rejected. Test no silent data merging and no credential logging.
- [ ] Run `python -m unittest discover -s tests -p test_physical_data_paths.py -v` and `node --test tests/runtime.test.cjs` from `desktop/`; confirm the new scenarios fail.
- [ ] Implement canonical root selection and coherent lifecycle handling. Replace generic “Video service” messaging with “Studio service”; distinguish initial startup from later child exit, expose safe reconnect/restart and retain useful logs. Never accept all Roaming/LocalCache as an allowed import root.
- [ ] Run focused tests plus existing desktop/runtime tests. Schedule a Windows manual smoke test from both a normal shortcut and a packaged Codex parent: inspect effective root, claim an image job, upload/return a real PNG, restart and reopen the same project. Use a temporary test project, no live database migration.
- [ ] Commit the reliability fix independently of the workflow features.

### Task 6: End-to-end contract verification and a controlled calibration trial

**Files**

- Create `backend/tests/test_calibration_workflow.py`, update frontend/desktop focused test scripts and `docs/CALIBRATION-TRIAL.md`.

**Interfaces**

- Use the public setup, project/contract, claim, execution-evidence, return, technical-review and human-calibration APIs from Tasks 1–4. No direct database edits or fabricated creator acceptance.

- [ ] Write an API integration test using a real fixture PNG and separate agent/human credentials: initial generator question → save built-in image/external video choices → creative intake → claim one representative still → record exact execution evidence → return PNG → agent technical review → second-image/provider/queue claim blocked → human rejection retained → targeted representative revision → human acceptance → next permitted image claim. Assert unchanged setup does not ask again and changed setup reopens the correct question.
- [ ] Run `python -m unittest discover -s tests -p test_calibration_workflow.py -v`; confirm failure before completing integrations, then pass without external generators or paid calls.
- [ ] Run the full backend suite with `python -m unittest discover -s tests -v`; from `frontend/`, run `npm test`, `npm run lint`, `npm run build`; from `desktop/`, run `npm test`. Fix regressions and record actual commands/results. These are planned checks, not checks already run for this planning document.
- [ ] Have the creator review the new workflow in a single calibration-only trial using the saved amber-flower reference. Verify the exact submitted prompt and applicable course-rule trace before any optional real generation. Obtain explicit permission before resuming the stopped creative trial.
- [ ] Record feedback, payload measurements and any remaining unverified capabilities. Do not claim the video pipeline works from a successful still, or publish an installer as part of source verification.
- [ ] Commit integration tests/docs and hand the source change over for review. Any installer build/deployment is a separate explicit delivery decision.

## Plan self-review

- Generator timing and once-per-project persistence: Task 1.
- Creator-controlled calibration, rejection and authority separation: Task 2.
- Partial-course source scope, actual prompt trace and retained owned outputs: Task 3.
- Measured payload bloat, catalog filtering, polling, cache/version correctness and compatibility: Task 4.
- Physical Windows roots and supervised lifecycle: Task 5.
- Public-API proof and controlled creator trial: Task 6.

Review the design and plan before implementation. Planning files only have been added; this plan does not authorize changing the running project, its approval switches, its historical reviews, or generating new media.
