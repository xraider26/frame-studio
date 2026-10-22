# Course-informed production recipes implementation plan

> Execute inline with executing-plans; one fresh whole-change reviewer at the end.

**Goal:** Apply the six approved improvements: traceable course principles, complete production recipes, motivated direction, specific quality standards, finished-production validation and equal Basic/Professional standards. Add three generated still examples for all nine built-in templates.

**Architecture:** Extend the current Studio rather than introduce a second workflow. A versioned recipe catalogue and source-rule ledger feed API/MCP, project context, prompt handoffs, exports, checks and a visual recipe browser. Saved projects retain their existing settings and human policies; activating the new recipe in an existing project is explicit and revision checked. New projects receive the recipe contract. Examples are illustrative AI stills, not tested video output or reference assets silently attached to jobs.

**Tech stack:** Existing FastAPI/SQLite/Pydantic, Next.js/React/CSS, built-in image generation, local PNG/WebP assets. No new runtime dependencies.

## Constraints and decisions

- User approved the six changes in chat; proceed without another approval round. Use feature/course-production-recipes in the current checkout, preserve all runtime projects and media.
- Import and hash the supplied review/playbook as source data. Full original course PDFs were not found in the checked locations; do not claim their catalogue is imported or invent page citations. Record corrected principles and studio-authored adaptation separately.
- Recipe choices guide the external agent; no hidden LLM, fake semantic scorer, or autonomous spending. Human approval policy and attempt/budget checks still apply.
- Three independent generated images per template, original prompts and provenance saved. Custom shows three possible treatments and imposes no genre. Images demonstrate direction only.
- Real finished-production assessments require an actual final video, selected compatible takes, recorded shot checks, human notes and explicit model/settings/source identity. Historical validation is scoped to that production; no guaranteed future quality or invented pilots.
- Basic and Professional are presentation modes only. Preserve overrides; apply recipe updates explicitly. Export the same versioned contract available through MCP.

## Review focus

- Legacy projects and saved snapshots must not silently gain new blocking rules or lost drafts.
- Agents must not enable/disable human QC policy, endorse their own work, or pass a final assessment using a placeholder/nonexistent file.
- Revisions, recipe versions and input changes must invalidate stale assessment claims rather than transfer proof.
- Generator handoffs must retain purpose, criteria and repair guidance for image-to-video as well as other profiles.
- Image examples must exist locally, have meaningful captions/prompts and remain distinguishable from actual production evidence.

## Tasks

### Task 1: Source ledger and executable recipes
- [x] Write failing backend tests for all nine distinct recipe contracts, source links, nonzero runtime allocation, purpose-based direction and legacy opt-in.
- [x] Implement `course_rules.py`, `recipes.py`; extend creative schema with versioned recipe choice and shot role/rationale; attach recipe context to templates, project reads, compiler, claims and exports. Add revision-checked explicit recipe activation and MCP tools.
- [x] Run targeted and existing tests; record results.

### Task 2: Contextual QC and finished-production evidence
- [x] Write failing behavioural tests for inherited template/role criteria and actual final-video assessment, actor/revision checks, input/settings scope and repeat trials.
- [x] Add recipe criteria to the shared checker; persist scoped final assessment evidence and summarize real trials, reported cost and defects. Keep existing saved-recipe endorsements intact.
- [x] Run backend suite and MCP transport checks.

### Task 3: Generated examples and recipe workspace
- [x] Generate and inspect 27 individual images; copy selected assets into frontend/public/recipe-examples and save exact prompts/provenance.
- [x] Add React interaction tests before implementing recipe browsing, image detail, rule explanations, activation preview and final assessment UI. Integrate with Templates, current project context and project creation.
- [x] Keep orange/glass styling, accessible controls and responsive image layout; avoid crowding the production workspace.
- [x] Run React tests, TypeScript/build and inspect actual page if browser access permits.

### Task 4: Review and local rollout
- [x] Fresh review; fix important issues with regression tests. Update coverage, MCP and recipe documentation with real limits.
- [x] Verify clean full suites/build; restart the existing local services without changing runtime projects. Verify HTTP/API and representative example asset URLs.
- [x] Commit changes locally; report exact functionality, evidence and any remaining external artistic validation. No GitHub push or paid video generation inferred.
