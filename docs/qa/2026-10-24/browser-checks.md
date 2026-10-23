# Browser checks — 24 October 2026

Checked the running local Orchestra Studio at http://127.0.0.1:3000/studio using the in-app browser. This is a focused interaction/visual check, not complete release acceptance.

## Verified

- Image/Video and Built-in/Saved template filters switch correctly. Seven image formats appear; image standards omit video acceptance/trials. Saved-library empty state is clear.
- Starting from Portrait preselects Image and Portrait in the creation dialog. Switching output to Video changes the available content templates and exposes video model/profile inputs.
- Created `Browser QA · Image` and `Browser QA · Video` with explicitly labelled QA model metadata. No generation was requested and no provider spending occurred. Existing `Trials` project was not edited.
- Image stages expose still-specific creation, take import/review and image handoff. Missing selected media has an explicit empty state.
- An unsaved Brief document survives navigating to Plan and returning to Brief document.
- Seven video sequence patterns are available. Podcast preview displays master/host/guest/reaction coverage and audio continuity. Applying the initial pattern changes the video project to revision 2. Selecting another pattern leaves revision 2 unchanged and Apply disabled until the replacement checkbox is checked.
- A bundled illustrative file (`frontend/public/recipe-examples/ai-film-1.png`) uploads to a saved production-bible entity. Thumbnail and large preview load. Upload advances entity version 1 to 2 and project revision 2 to 3.
- Detaching and saving advances project revision to 4; after reload the checkbox remains unchecked and the file remains available to preview/reattach.
- At 390 × 844, mobile navigation expands to all five stages. Image export and reference-preview page widths do not overflow horizontally (viewport 390; document scroll width 375). Preview image bounds are x=43..332, width 289, and the image is loaded. Desktop viewport restored afterward.
- Captured browser warnings/errors were empty at the reference-preview checkpoint.

## Findings requiring follow-up

1. The project next-action banner and queue cards show the full agent-oriented missing-intake instruction block, including MCP method/property names. This overwhelms the creator UI, especially on mobile. Replace with a concise creator-facing next action while retaining full guidance for agents.
2. Image project home shows `30 s target`; generator handoff shows `30 s retained`. Visual concept also says to time beats before generating. These video-oriented labels are misleading for still-image projects.
3. A `Sequence applied` success message persisted when switching from the video project to the image project. Clear project-specific notices on project changes.

## Limits and retained QA data

The two clearly named QA projects remain in local storage for inspection. The image project contains one detached illustrative reference. The video project contains a podcast coverage plan. Models are QA labels, not configured providers.

This pass did not exercise real generation, a finished media approval/export lifecycle, saved-template restoration, every format/pattern, a packaged installer, or comprehensive mobile form interaction. Do not treat this as full release sign-off. No application code was changed in this pass.

Evidence: [desktop reference preview](reference-preview-desktop.png), [mobile reference preview](reference-preview-mobile.png).
