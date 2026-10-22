# Course source grounding

`docs/sources/verified-course-lessons.json` is the source of truth for original-guide verification. It contains file SHA-256 hashes, PDF page counts, the exact pages inspected, stable lesson links, concise paraphrases and separately labelled studio corrections. Page numbers are one-based file pages, including covers.

The supplied `AI_Video_Course_Review_and_Workflow.md` reports a wider review of 45 PDFs. That historical claim is not independently established by this implementation. Only the originals and pages listed in the JSON ledger are verified here. Extracting text from a whole file does not mean every page or illustration has been reviewed.

Production recipes remain studio-authored adaptations. Existing rule IDs and review provenance are retained. Supporting citations identify the linked principles; `correction_citations` identify examples that the studio repairs. A source instruction is not proof that a generator obeys it, and a source model setting is not a validated current Flow capability.

Original PDFs and complete extracted text are private, git-ignored files under `studio_data/course_sources/`; they are not needed to serve the committed paraphrase ledger. Stable classroom links may require course access. Do not commit signed download links, credentials or original course files.

Verification does not establish that lesson videos were watched, all course attachments were recovered, provider settings are current, claims or testimonials are true, or finished recipe videos have passed quality review. Inspect `coverage` and each source's `review_scope` before presenting coverage figures.

Directing coverage includes source-motivated lighting, shadow quality and material response; visually inspected angle, shot-size and optics examples; and depth layers, atmosphere, composition and lead room. Optical labels remain approximate appearance cues. Lighting continuity preserves physical source placement while screen direction changes with viewpoint.
