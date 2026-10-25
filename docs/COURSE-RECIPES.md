# Production recipes

Open `/studio` and choose Template library. The nine built-in formats are AI film, UGC, short drama, advertisement, explainer, podcast, 2D animation, claymation and custom. Each has three generated example stills. Open an image to inspect its full composition, exact generation prompt and the direction it illustrates. These independently generated stills are examples, not validated video productions or guaranteed continuity references.

A recipe defines reference preparation, planning decisions, timed shot roles, camera/light suggestions, sound direction, acceptance criteria and focused repairs. The external agent must adapt these decisions to the idea and verified generator capabilities. The studio supplies structured guidance; it does not contain an internal script-writing model or automatic aesthetic scorer. Basic and Professional change how much detail is shown, while preserving the same standards.

New built-in projects activate the current recipe. Existing projects show an explicit activation control; activation requires the current revision and a human action, preserves creative overrides and approval policy, and reopens affected reviews. Saved templates retain recipe identity/version. Applying a look from another format preserves the destination format's recipe. Settings-only templates inherit their saved camera/light defaults and reallocate fresh placeholder shots to the restored runtime.

Agents can read `recipe_catalog`, current project recipe context and `recipe_trials`. Compiled generation handoffs, queue work and generator ZIPs carry the same versioned contract. The ZIP adds `production-recipe.json` and readable `production-recipe.md`. Agent calls cannot change recipe policy through saved settings or record human final assessments.

## Finished-video assessments

The Video trials tab records a human review of a real imported final video. Select it in final review first, complete the actual shot checks, record the confirmed model/settings and source/date, then inspect beginning, middle and end and watch the complete final cut. Every final criterion needs an explicit pass/fail, with notes and defects. A failed production is useful evidence too.

Passing requires compatible selected source takes, valid retained source ranges, expected runtime/framing and all final checks. Evidence records project inputs, selected source files, final-file hashes, attempts, reported costs and model scope. Changing inputs or deleting/replacing a source makes the old assessment stale. Duplicate assessments of the same output do not count as independent successful productions.

Historical summaries describe reviewed productions, distinct ideas/models and defects; they do not establish guaranteed future quality. No paid artistic pilot or real final-video assessment was fabricated for this release. Synthetic video fixtures validate the software only. Repeated real production trials across ideas and generators remain necessary to demonstrate consistent artistic results.

## Sources

The supplied review and selected original PDF pages are tracked separately from studio-authored adaptations and corrections. The [source ledger](sources/verified-course-lessons.json) records exact verification scope; [source notes](COURSE-SOURCES.md) explain the remaining gaps. Private original PDFs stay in ignored local storage and are not required to run a fresh checkout.


### Per-take rule and request evidence

New claims snapshot a `rule_application` manifest. Recipe-owned metadata supplies requiredness, phase, stages, role scope and declarative predicates. Required applicable pre-generation rules need a concrete populated compiler/reference binding; missing mappings, required references and unverified prerequisites block execution. Optional unverified guidance remains visible. `not_applicable` is computed from the saved scope and predicate, never an agent waiver. Required identity/product requirements remain in `production.reference_requirements`; calibration scope only limits the representative baseline.

A mapped media-review criterion has a pending outcome until the actual take is inspected. Editing rules apply at their named editor/final-review stage. The per-take evidence view displays compiled/submitted prompts, reference versions, argument payloads, source attribution, scoped mappings and actual inspection separately. A mapping is traceability, not proof the generated picture followed a rule or creator acceptance.

The compiler preserves authored punctuation, exact text and custom-template syntax. Explicit subject/environment prose precedes duplicate bible contributions. Administrative intent, sound and review notes stay outside still-image visual prose. A required rule omitted by a custom template needs an explicit saved-template revision rather than a silent prompt rewrite.

The mutable-state rule stays a required pre-generation rule where applicable. Its trusted `video_continuity` predicate excludes an initial scene with no preceding shot or explicitly tracked state; subsequent shots and explicit state tracking require populated continuity bindings. This does not waive any saved identity/product fidelity requirement.
