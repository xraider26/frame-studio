# Frame Studio: creative production system

Status: approved by the user on 21 October 2026; implementation authorized. The user also requested contextual (?) help with visual examples, available on hover and click.

## Intent and existing decisions

Make the studio a practical directing and production system informed by the user's supplied course material. A creator or MCP agent should be able to express a specific artistic intention, develop it into a coherent shot plan, generate through their chosen tools, evaluate the returned media and revise a named defect. Advanced controls must affect actual handoffs and exports; decorative controls are a failure.

The conversation establishes: orange and glass visual design; saved selectable projects; content templates; optional API generation; external agent/export generation without an API; generator-dependent prompts; MCP access for multiple clients; user-controlled approval at each workflow step; editing in the user's existing software; local media storage rather than mandatory cloud hosting. Preserve working project duplication, recoverable Trash, real-file validation, credentials separation, revisions, stale-output handling and immutable jobs.

This design addresses the omissions listed in the audit. It does not promise that a generator will obey every direction or that software tests prove artistic quality. The user's imagination should not be constrained to preset choices: each creative field accepts custom direction and each technique has editable parameters.

## Source grounding

Known source: `C:/Users/Reforged/Downloads/AI_Video_Course_Review_and_Workflow.md`, a supplied review and production playbook. Its account of reviewing PDFs is not this implementation's independent review of those PDFs. Locate the original downloaded guides/transcripts before claiming their full technique catalogues are included.

Create an indexed knowledge collection of sources, techniques and corrections. Each entry records source title, available source file, section/page when actually verified, extraction/review status, plain explanation, narrative use, editable defaults, failure risks, safer alternative and applicable formats. Distinguish extracted teaching, the playbook's corrections and newly authored studio recommendations. Do not invent page citations or fill a named 37/30/24/16/10-item collection from memory and label it complete. The UI and MCP expose coverage and unavailable sources explicitly. Preserve human-authored source text as source data, not instructions to execute.

Useful material to encode includes AVB shot descriptions, framing/depth, camera movement, lighting/mood, styles/colour, hooks/frameworks, character sheets, motion reference compatibility, format-specific planning, timed dialogue, continuity, QC and pilot learning. Exclude the unsupported growth claims and defective examples identified in the review. Source text is not silently changed to remove an error: attach a correction and use the corrected planning rule.

## One shared project model

Extend the existing local API/store and Next.js app; do not create another disconnected prototype or a second workflow engine. Proposed implementation choice: versioned nested records, validated on the backend, with a shared published JSON schema for MCP and clients. Existing project and shot IDs remain stable. Read-time defaults preserve legacy projects; an explicit save upgrades them. Back up the database before any persistent migration.

Project records contain:

- Creative brief: premise, viewer promise, audience, platform, format, niche, opening/payoff, factual requirements and sources, target duration/aspect, pilot limits and references.
- Story: alternative hooks, chosen hook, framework independently selected from visual format, timed beats, narration/dialogue, visual action, caption/end-card notes, facts versus dramatisation.
- Production bible: characters (identity, canonical views, costume variants, voice), locations (layout and physical lights), props (appearance), visual style/palette/material rules and sound direction. Entries have stable IDs and versions, and can link real imported references.
- Generator setup: selected profile/model, generation mode, actual observed capabilities/settings, source/evidence and observation date, desired settings separately from confirmed controls.
- Resource policy: credits or one currency per project, total and pilot limits, maximum attempts per shot, cost evidence, spending ledger and reservations. Unset limits and unknown prices are visibly unknown, never zero or unlimited by implication.
- Ordered shots, immutable generation attempts, selected takes, reviews, editing notes and learning records.

The existing generic brief/script documents remain readable and editable alongside structured data. An agent may write their content; the studio is not assumed to contain an LLM or to autonomously invent an excellent script.

## Structured shot card

Preserve shot ID separately from scene ID, edit order, generation job and selected take. Each card has the following groups:

1. Story: purpose, script beat, subject, environment, mood, generation duration, retained edit duration and optional cut/transition explanation.
2. Camera/composition: shot size, angle/position, lens feel/focal-length cue, aperture/depth cue, camera/body look cue, foreground/midground/background, lead room, screen direction, main movement, speed, start/end framing and movement timing. Brand/lens values describe a visual intention, not simulated physical fidelity.
3. Lighting: technique, physical source(s) and location, camera position, derived camera-relative direction, softness, contrast/shadow depth, colour temperature/tint, practicals and material response. Do not copy camera-left across reverse shots as a world-space fact.
4. Art: style, palette, texture/material and shot overrides. Inherit project values when unset; show their origin. An explicit override replaces the inherited value rather than appending a conflicting instruction.
5. References: bindings from actual upload slot/role to asset ID and version, character/costume/location/prop IDs, optional start/end image, motion source and compatible pose/framing notes.
6. Action/continuity: opening state, one primary action, optional timed action beats, ending state, visible characters/headcount and transition explanation. State is typed key/value data attached to bible entities, with screen direction and light/time when relevant.
7. Sound/performance: active speaker, dialogue, narration, measured speaking duration and pauses, voice direction, ambience, foley cues, music intent and captions. Listener cutaways can retain speaker audio without instructing the listener to speak.
8. Acceptance/revision: per-shot criteria, technique/source links, known defects, revision reason, original/edited comparison, chosen take and review evidence.

Fields are optional during drafting. The production validator identifies missing required inputs for the selected generation mode before dispatch. A fast simple shot remains possible; advanced sections expand as needed. Do not force every production into every field.

## Studio interface

Keep the existing workspace/project selector and visual identity. Proposed navigation groups:

- Overview: workflow progress, next action, unresolved production issues, pilot/budget state.
- Story: brief, hooks/framework, timed beats and runtime totals.
- Production bible: characters, locations, props, style and linked reference images.
- Shots & direction: ordered shot strip and one selected detailed shot card. Tabs for Story, Camera, Lighting, Art, References, Continuity, Sound and Quality. Each section can use a technique or custom direction. Provide compact summaries so the user can scan a sequence without opening every field.
- Technique library: search/filter by purpose, category and format; explanation, example, risk, editable parameters and source/coverage. Apply to a project or selected shot with a visible change preview. Presets do not overwrite unrelated work.
- Workflow & reviews: existing approval switches, relevant checks/evidence, returned media, beginning/middle/end inspection prompts and actionable feedback.
- Generator handoff: compiled prompt preview, selected mode/model, capability observations, validation, reference slots and export.
- Takes & learning: preview/compare real takes, selected take, defect/revision log, attempts/resources and manually supplied performance data.
- Editor handoff and Connections & MCP remain accessible.

Use progressive disclosure, accessible labels, keyboard controls, clear focus, legible glass contrast and responsive layouts. Preserve unapplied edits during polling. A revision conflict must show recovery choices without dropping drafts or overwriting another client's changes. Applying a preset is reversible before saving.

Technical option labels include a (?) control. Hover and keyboard focus show a short explanation with a visual preview; click/tap pins the popover so it can be read and interacted with. Escape, close and outside click dismiss it. Keep the preview within the viewport on narrow screens. Show the selected option's actual meaning rather than a generic definition. Framing/lens/light/movement examples use a consistent scene and explicitly identify illustrative diagrams/look approximations; camera-brand presets are not certified camera simulations. Include use cases, tradeoffs and source provenance. Custom values remain editable and receive category help without inventing an exact visual prediction.

## Templates with production behaviour

Separate story framework, content purpose and visual treatment. Retain the existing content choices and add editable format rules and acceptance checklists:

- AI film/short drama: motivations, staging, opening/ending state, identity, object and screen continuity.
- UGC: hook/demo/payoff, believable handheld restraint, native contrast/saturation choices and reference/product fidelity.
- Advertisement: audience awareness, desire/objection, credible benefit, proof/source and appropriate CTA. Do not invent testimonials or evidence.
- Explainer: promise, progression of understanding, factual sources and illustrative visual distinction.
- Podcast: host/guest assignments, studio layout, speaker audio and listener reactions.
- 2D animation: canonical character, expression/wardrobe, consistent metaphor, line/material/colour rules.
- Claymation: tactile materials, miniature scale, deliberate movement and foley.
- Custom: unrestricted fields and custom rules.

Templates seed a workable structure and suggested techniques, with the reason visible. They do not fill final creative content with fake completed work. Beat durations are recalculated to the target runtime; scratch-read durations are measured or explicitly marked estimates.

## Compile, validate, execute and revise

One compiler produces the browser preview, immutable job handoff and ZIP prompt content. Resolve inheritance, references and continuity before formatting. Image prompts describe observable appearance; motion prompts emphasise intended change. Keep voice/audio/negative notes separate when the chosen generator requires it. Custom templates gain documented advanced fields without breaking existing placeholders. Profiles for additional named generators are authored only with traceable documentation/observed capabilities; unverified modes are labeled and cannot masquerade as supported integrations.

Validation results contain a stable rule ID, severity, shot/entity/path and a specific correction. Blocking errors include unresolved required assets/versions, duplicate upload slots, impossible numeric timing, retained duration exceeding generated duration, unsupported verified settings, unknown required execution cost under a configured hard budget, and exhausted resource/attempt limits. Warnings include missing observations, continuity mismatches without explanation, runtime mismatch, dense action, unmeasured dialogue and possible text contradictions. Heuristics are labeled; they are not semantic understanding or full visual QC. Review all planned shots when generating a whole export, and the actual shot/mode when claiming a task.

Approval policy remains human-controlled. Automatic mode does not bypass blocking production errors or resource limits; it means validated outputs and required recorded checks can proceed without human approval. Reports supplied by agents identify the agent and are never labeled human approval. A human can resolve a warning with a recorded explanation. No agent tool may disable gates or forge human review.

Each returned output remains an actual validated file with an immutable input snapshot. Record cost, time, defect and criteria evaluation per attempt without silently rewriting old history. New takes can be compared and explicitly selected; returning a file alone is not evidence that it passed visual/audio criteria. Configurable QC requirements decide which evaluations must be recorded before progression. Existing projects retain their current policy until the user opts into newly introduced criteria.

Targeted revisions reopen only affected shots and dependent references/continuations/reviews. Retain unrelated selections. A changed image invalidates motion relying on it; an audio/edit-note-only change must not discard an unrelated keyframe. A stale job return remains stored but cannot become the active take without explicit compatibility review. Validate these dependency rules before relaxing current conservative invalidation.

For requested final-frame continuation, extract a real selected frame locally with FFmpeg, register it as a versioned reference and show the image for inspection. Chain only shots explicitly linked by the creator and only through supported generator modes. Revalidate continuity rather than treating extraction as proof of continuity.

For local image repairs, prepare an editing handoff containing original asset, region/mask reference where provided, requested defect repair and preservation criteria. The actual editing tool remains the user's agent/API tool. Compare its actual returned file with the original. Do not claim an inpainting/upscaling backend exists until connected and tested.

## Resource policy and learning

Reserve an evidenced planned cost atomically when submitting through studio API or claiming an externally budgeted job. Settle against reported actual cost; record an unknown/exceeded amount honestly. Concurrent claims cannot oversubscribe a configured budget. Canceling locally does not refund an already submitted vendor job. Claim retries remain idempotent; no automatic paid retry. External spending is reported by the executor and cannot be policed outside this studio; display that boundary.

Report attempts, known credits/currency, cost per selected usable shot, production time and defect types. Performance/retention/CTR fields accept actual manually imported measurements with source/date and experiment notes; there is no implied analytics-account connection. Separate story demand from production defects and compare one deliberate change at a time.

## MCP and external editing

Publish schemas plus source-linked knowledge/search, structured project/shot/bible updates, compiled prompt preview, validation, take/defect/QC recording, resource reporting and editing/continuation handoffs through the existing server. Existing tools remain usable, with versioned extensions and explicit validation errors. All mutations use revision checks and the existing authority boundary. Do not require each client to reconstruct creative data from prose. Document supported operations with a real end-to-end client test.

The export ZIP contains versioned project/scene/shot/take IDs, effective direction, actual slot-to-asset references with portable paths, prompts, dialogue/audio timing, before/after states, acceptance criteria, source links/coverage, validation report and return contract. Its approval state is a dated snapshot; execution always consults live policy. A package never contains provider credentials.

The editor package contains chosen real media, retained timings and source in/out ranges, dialogue/audio/caption/cut notes, continuity and colour intent, plus missing-file/runtime warnings. A readable manifest/CSV is sufficient initially; no native editor-project compatibility is claimed. Editing and publishing remain external; no built-in CapCut clone, publishing automation or mandatory cloud storage is added.

## Delivery order and acceptance

These milestones are a connected upgrade, not separate replacement apps. This ordering is a proposed engineering choice.

1. **Source and record foundation:** coverage ledger, validated versioned creative model, inheritance, legacy round-trip preservation and schema docs.
2. **Directing workspace:** structured story/bible/shot UI, source-linked technique selection, custom options, format-aware templates and drafts/conflict recovery.
3. **Executable direction:** shared compiler, preflight checks, exact reference maps and advanced data through MCP/API/ZIP/editor handoff.
4. **Production iteration:** contextual QC, evidence and take comparison/selection, selective revision invalidation, real frame continuation and image-repair handoffs.
5. **Resources and pilot learning:** attempt/cost limits and ledger, useful metrics, final end-to-end pilot and documentation.

Each milestone needs backend behavioural tests, MCP contract tests where affected and browser verification of the actual controls. Include old project fixtures, invalid references/timings, stale/concurrent changes, auto/manual policy, targeted revisions and budget race/idempotency cases. No paid generation is needed to test data flow; synthetic fixtures are labeled.

Before claiming production quality, run a real representative pilot using an available, authorized generator and inspect the complete output against recorded artistic criteria. A disconnected provider, absent original source, or missing paid authorization is reported precisely; it does not stop unrelated implementation or justify fabricated completion. Finish with a requirement-to-feature/test coverage report, including remaining gaps.
