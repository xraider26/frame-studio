# Image prompting and ComfyUI implementation plan

> Execute inline with the executing-plans and test-driven-development skills. User approved the described prompting/workflow upgrade and explicitly included direct execution.

**Goal:** Improve still-image direction and run explicitly mapped image/video ComfyUI API workflows through Orchestra's existing tracked provider jobs.

**Architecture:** Keep generator profiles separate from execution connections. Add validated per-shot image requirements and a focused renderer. Add a ComfyUI connector using the existing provider lifecycle, authentication, request limits, media validation and revision checks. Each user-owned connection contains one API workflow, media kind and explicit input/output bindings. Preserve all unmapped values, especially checkpoints and sampler settings. Never install models/nodes or run generation during development verification.

**Tech stack:** Existing Python/FastAPI/httpx/Pydantic and React/Next.js; no new dependencies.

## Constraints and decisions

- Remain in the user's current development checkout; preserve existing QA artifacts and project data.
- Image requirements: mode generate/edit, edit instructions, preserve instructions, exact text, layout, background. Reference roles use existing shot bindings.
- Add Qwen image and MiniMax H3 profiles with official-source guidance; unknown versions remain unverified.
- Import API-format JSON only; UI-format graph exports receive an actionable error. Bindings identify node/input for prompt, optional negative/seed and references by existing slot; output node is explicit. Seed is preserved unless explicitly configured.
- Validate workflow structure at save; check installed node schemas/model dropdown values before submission. Track remote prompt ID without treating a timeout as success. Image outputs PNG/JPEG/WebP; video outputs MP4 through the existing media validator.
- Serialize this connector's jobs per ComfyUI endpoint. Do not interrupt a shared ComfyUI server on shutdown. Interrupted jobs require checking the remote outcome before retrying.
- A portable workflow handoff must include bound prompts and reference instructions without credentials. Exporting never grants permission to bypass project gates.

## Tasks

- [x] 1. Add failing behavioral image tests: edit/preserve/layout/exact text survive compilation, custom prompts remain intact, conflicting default exclusions warn, reference roles stay explicit, model variants/unknown versions stay truthful. Implement schema/renderer/profiles; add controls and invalidation coverage.
- [x] 2. Add failing connector tests: mappings preserve template, UI format/duplicate targets/output mistakes reject, unavailable nodes/models fail, image and MP4 result selection uses mapped output only, execution errors/timeouts/oversize fail, reference paths stay inside media storage. Implement connector and provider integration.
- [x] 3. Add user controls for adapter/media kind/workflow import/bindings, connection validation and portable workflow export. Verify existing JSON connections remain compatible and credentials stay private.
- [x] 4. Run backend/frontend/desktop checks and build; fresh review for important gaps, fix with regression tests; document setup and explicit live-GPU validation limits.

## Review focus

- No appearance/style additions override the creator's illustrated or edited image.
- Missing or extra reference bindings cannot silently fall back to unrelated images.
- Native workflow defaults and seed survive unless explicitly mapped.
- Execution history failure or wrong output node can never become successful generation.
- Workflow settings can contain private endpoint information: connections remain local/user-controlled and credentials never enter portable exports.

## Execution ledger

- Initial repository has only untracked docs/qa artifacts from the preceding browser checks. Existing development branch retained.
- Full backend suite: 186 tests passed after image/connection review fixes. Final additional oversize-download regression and named download-limit constant were verified with the 15-test connector/provider subset; all passed. Image compiler subset: 7 passed. Frontend: 66 passed. Desktop: 12 passed. Production build passed using bundled Node v24.22.1; whitespace check passed.
- Fresh review found uint64 seed rounding, implicit edit-source fallback, inherited edit appearance defaults, native LoadVideo.file bypass and disabled queued-connection submission. All were fixed with observed red/green regressions. A final export-note consistency regression also passed.
- Ruling: raw workflow JSON remains text through the browser transport and is parsed in Python; native JavaScript numbers cannot preserve uint64 seeds. Import resets mappings because a new graph can have different node IDs.
- Ruling: keep legacy polish adapter unchanged and expose the new native adapter through existing tracked providers; the new connector never uses the legacy offline image enhancement.
- No ComfyUI listener on the default 8188 port. No live GPU/model inference claimed. Automatic approval review rejected isolated QA server launch as blocked by policy, so new browser smoke testing remains pending. Existing user services/data were not restarted or edited. Source changes are local; no merge, push, installer or release created.
