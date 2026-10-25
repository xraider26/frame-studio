# Orchestra calibration and connected-agent workflow

Status: proposed design for review; no application changes authorized or implemented by this document.

## Intent and confirmed requirements

Orchestra must carry a creator's intent and the applicable bootcamp guidance into actual generator execution, expose departures, and keep creator acceptance separate from agent inspection. The recent surreal-world trial exposed failures in that chain despite successful job claims and media returns.

The creator explicitly wants connected AI to ask which generators will be used immediately upon invoking Orchestra. Confirmed frequency: **ask once per project; ask again when changed**. Image generation may use the connected agent's built-in tool, whose underlying model/version is opaque. Videos may use a separately named external tool; a label is not evidence of an API connection or verified capabilities.

Current trial remains in calibration. The creator rejected all three generated images. Two have agent technical reviews; neither has creator style approval. The supplied amber-flower image is the calibration reference. No new generation, alteration of historical reviews, or automatic adoption of rejected media is part of this planning task.

## Proposed product decisions

These defaults are recommendations, not additional preferences attributed to the creator.

1. New projects begin in calibration. Exactly one representative still can be generated and technically reviewed before a creator accepts the visual baseline. The creator may explicitly skip calibration in the UI. Existing projects retain their policies and are offered an explicit opt-in; old technical passes never become baseline approval.
2. Ask one grouped generator question before creative intake or technical choices. Reuse the answer across sessions. Image-only projects require only image setup. Video projects ask about images and video together. A creator can name an external video destination without connecting it; this does not block permitted image calibration.
3. Accept managed tools without inventing an exact model/version. Store executor, tool/provider label, profile, optional model/version, provenance of the creator's selection, and separate observed capabilities for each medium.
4. Preserve complete job evidence internally, but return a compact execution packet by default. Fetch full provenance and catalogs deliberately rather than embedding them in every handoff.
5. Expose applicable course rules, their source scope, their application to prompt/review/edit fields, the compiled prompt, and the submitted prompt. Do not claim complete course coverage or verified artistic compliance from a manifest or agent attestation alone.

## Generator entry and persistence

Add a read-only `start_project_setup(project_id=None, output_type=None)` MCP/API operation. Without a project it returns the initial question and required fields; with a project it returns only missing/changed setup. `studio_capabilities` and MCP initialization instructions direct connected agents here first and expose the same concise initial action. A skeleton project may be created to save the conversation, but creative preparation and claims remain gated.

The initial question is: “Which generators will you use for images and videos? You can use this AI's built-in image tool, another app, or a connected service.” For an image-only project, omit videos. If output type is unknown, ask whether images, video, or both are needed before requiring a video choice. If the creator already supplied choices in the invoking message, save them rather than repeating the question.

Add project `generation_setup` with version, image/video selections and a selection fingerprint. Each selection has `executor` (`agent_builtin`, `external_handoff`, `api`, `comfyui`), `tool_name`, `profile`, nullable `model`, `model_version_status` (`specified`, `managed`, `unknown`), nullable `connection_id`, `selection_source` (`creator_statement`, `creator_delegation`, `legacy_unconfirmed`, `template_unconfirmed`) and `source_text`. Agent assertions about the conversation are recorded as assertions, not proof of human UI approval. Unknown versions are legitimate; unknown capabilities stay unknown.

`set_generation_setup(project_id, setup, expected_revision)` records a supplied/delegated choice. Keep existing generator settings synchronized for existing compiler/export paths. Template/legacy defaults are suggestions until confirmed; retries, sessions and template reuse do not manufacture confirmation. A relevant setup change reopens only that medium's setup/capability state and affected outputs, and changes the workflow contract. An image-only project later changed to video asks only for the added video choice. An explicitly deferred video choice is visibly incomplete and blocks video generation, not image calibration.

The service cannot force arbitrary third-party AI to ask a conversational question before any tool call. It can advertise the question at entry and reject creative writes/claims until setup is satisfied. Connection status must distinguish saved external destination from executable API/ComfyUI access.

## Calibration and review authority

Add project `calibration`: `mode` (`calibration`, `production`), `status` (`not_started`, `pending_creator`, `approved`, `rejected`), `representative_shot_id`, nullable `baseline_asset_id`, baseline/reference version fingerprint, decision history and feedback. The generation permission is computed from this state on every claim, including queue/batch dispatch and API providers.

During calibration, generate only the representative image. Returning it and passing technical checks yields `await_calibration_approval`, not permission for another image. Rejection preserves the take, records feedback and permits a targeted replacement for that representative shot only. The human-only `review_calibration(..., approve, note, expected_revision)` approves or rejects the current non-stale take. Agents can relay rejection/stop feedback and block their work, but cannot assert creator acceptance, change calibration mode or skip the gate.

Use two separate signatures. `style_contract_signature` covers approved style-reference IDs/versions, shared visual treatment/continuity constraints, calibration scope and the image executor/model selection. `baseline_take_signature` additionally covers the accepted representative take and its own compiled prompt/reference fingerprint. A relevant change to either revokes the affected acceptance. Adding a different world/scene prompt under the unchanged shared style contract does NOT revoke the baseline. Changing only the future video destination likewise does not. Explicit per-shot overrides of approved style constraints require shot-specific creator acceptance before that shot can count as production-ready; the server detects structural override changes, not semantic artistic similarity.

Reference requirements are scoped before generation. Add `reference_requirements` entries with entity/kind, purpose (`style`, `identity`, `product`, `layout`), requiredness and source rule. Environment calibration can use the supplied style screenshot and written environment design without claiming face/identity fidelity. A request that explicitly requires a recognizable character or faithful product keeps canonical identity/product references required; absent references yield `ask_creator` to provide them or explicitly narrow calibration scope. Only the creator can narrow a required fidelity scope. A generic recipe reference-match criterion is instantiated for the actual required purposes, not asserted universally when none exist. Optional irrelevant purposes may be `not_applicable` with a deterministic applicability reason; missing required references remain `blocked`.

Technical reviews show inspector and scope; creator acceptance shows a separate actor/time. Historical agent passes remain historical agent passes. An agent cannot turn a required reference check into not-applicable, invent reference approval, or reuse an environment-only approval as approval of character likeness.

## Course-to-output trace and prompt fidelity

Use only the active recipe version, stage and role. Applicable rules retain IDs and original-page/source scope. The current source coverage is partial (the repository describes ten recovered PDFs and 66 selected verified pages); review-derived summaries and studio corrections remain distinguishable from original verified pages. Include model-specific guidance without treating it as a guarantee or connecting an account.

Each packet contains an application manifest: rule ID/version/source locator; status (`applied`, `not_applicable`, `unverified`); and the corresponding prompt field/span, reference binding, review criterion or external editing note. Extend active recipe rule metadata with `required`, `stage`, `role_ids`, `phase` (`pre_generation`, `media_review`, `external_edit`) and declarative applicability predicates. Do not reclassify the entire source corpus as mandatory: preserve current recipe requirements and have new applicability classifications reviewed in the code change.

For a required applicable pre-generation rule, only `applied` with a resolvable binding satisfies readiness. `unverified` blocks with the missing prerequisite. `not_applicable` is allowed only when the rule's predicate is false for the saved creator-approved scope, with the predicate result/reason stored; an agent assertion alone cannot waive it. Optional unverified guidance is disclosed without blocking. A required media-review rule is mapped to a concrete criterion before generation; its outcome remains pending until actual inspection, so the application status must not masquerade as a pre-existing image pass. External-edit rules map to editor requirements and block only their relevant delivery stage. Presence of a mapping proves traceability, not that the image obeys it; media evidence and creator acceptance remain separate.

Compile visual content once with documented precedence: explicit shot override, shared defaults, then recipe suggestions only for unset fields. Preserve exact text/custom syntax. Avoid repeating an environment or entity description already included in the selected primary field. Keep administrative uncertainty/provenance outside the generator prompt.

Add `record_generation_execution(job_id, execution, expected_revision)`. Execution stores tool identity, exact submitted positive/negative prompts, actual reference IDs/versions, supplied arguments and a hash. Server-run providers record automatically. External agents report this evidence; label it `agent_reported`, not independently verified. Only line-ending normalization is automatically equivalent. Other prompt changes require a revised claim and renewed creator acceptance where applicable; the service does not attempt to infer semantic equivalence. Existing owned output must remain returnable, with changed/missing execution evidence retained as `needs_review` or stale rather than silently discarded or accepted as current.

## Compact handoffs and catalogs

Measured job-02: 309,079 minified UTF-8 bytes; duplicated top-level and nested handoff. One handoff's recipe contract is 135,786 bytes, including 86,098 bytes of coverage and 36,978 bytes of source rules. Removing duplication and that whole contract gives a diagnostic 93.9% byte reduction, but relevant rules must be added back. This is not a token-billing measurement or an achieved implementation saving.

Execution packet schema v3 contains one job summary, one handoff, applicable rule slice, contract/version hashes, exact prompts, bound reference paths/versions, necessary media requirements, policy/resource/preflight state, unknown capability/cost status, job ownership/signature and exact return contract. It omits the full project, all-stage recipe, full source catalog and unrelated examples. Shared details are available by versioned targeted reads; cached context cannot authorize stale policy.

Extend `claim_generation` with `response_format='compact'|'legacy'` (default compact). Preserve top-level `handoff`, `job.id`, request IDs and `already_claimed`; nested `job.handoff` is only available in explicit legacy format. Keep stored v2 handoffs immutable and compact them only when serializing responses. Make this response-shape change explicit in schema-v3 release notes. `get_job(detail='summary'|'execution'|'full')` defaults to summary. Existing returned media and ownership/idempotency behavior are preserved.

Add filters to catalog reads: recipe ID, stage, role, summary/detail, provenance inclusion and pagination. Bootstrap excludes embedded creative schemas and full coverage. Full sources remain retrievable with stable locators. Project polling must likewise avoid retransmitting every job's full handoff; provide `get_project(detail='summary'|'full')`, with summary excluding job payloads and full retained for diagnostics/export.

Proposed initial fixture budgets: bootstrap at most 16 KiB minified UTF-8; a representative single-shot packet at most 12 KiB. General packet ceiling 64 KiB; oversized legitimate content returns `payload_too_large` with field-size diagnostics and a remedy before any generation. Never truncate required policy/prompts/references to satisfy a budget. Measure exact tokenizer counts separately with a declared tokenizer; byte checks are deterministic cross-environment regression checks.

## Windows reliability follow-up

Keep a separate implementation task for physical writable-root resolution, shared desktop/MCP discovery, instance ownership and lifecycle diagnostics. Preserve data and credentials. Do not broadly accept the entire AppData tree or remove containment checks. Test packaged-launch redirection explicitly: a file may resolve into Codex LocalCache while an existing logical Roaming directory does not. Report physical roots without credentials, atomically publish ready discovery, clear only owned discovery, and distinguish startup failure from a later supervised-child exit. Recovery should restart the owned service/app coherently, not encourage replacement of supervised children.

## Delivery and acceptance

Order: generator intake; calibration/review authority; rule/prompt traceability; compact transport; Windows reliability; then one controlled calibration trial. Each task has a complete test cycle. No provider calls, new artwork, data migration, installer publishing or automatic repair of live projects is needed to implement or test the code contracts.

Success: a newly invoked connected agent presents the generator question first, remembers the creator's answer per project, emits one reference-anchored calibration image, stops for creator approval despite an agent technical pass, exposes the actual prompt/rule mapping, and returns compact packets without weakening gates. Existing projects and stored jobs continue to load, and their historical checks are not upgraded into creator approval.
