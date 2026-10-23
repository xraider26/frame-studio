# Orchestra — image projects and creator-led production

Date: 23 October 2026. Development branch: `feature/image-projects-creative-intake`.

The product is now **Orchestra**, formerly Frame Studio. The interface, desktop shell, icon and future installer name are updated; installation identity, existing storage and MCP configuration keys remain stable. The GitHub repository path is unchanged.

Additional next-beta work: mandatory per-project MCP workflow contracts with persisted actor acknowledgements, revision/workflow enforcement and policy/model invalidation; the [reviewed shared prompting guide](PROMPTING-GUIDE.md), five editable style setups and FLUX/Midjourney profiles. See [agent bootstrap and compatibility](MCP.md#strict-agent-contract-next-beta-source). Acknowledgements do not prove inspection or guarantee a model's behavior outside the app.

## Goal and release boundary

Turn an idea into repeatable, carefully directed image or video production, using the creator's chosen generators. Preserve creative control, references, quality evidence and actual media throughout. The app coordinates agents and tools; it does not include a generation model or guarantee artistic quality.

The repository was returned to **private** at the owner's request. Do not make it public again without a new instruction. The existing `v0.2.0-beta.1` installer remains the earlier release; source changes on this branch are not automatically included in that installer. Do not overwrite its assets or move its tag.

## Requested behavior

- **Output choice:** new projects choose Image or Video. Image projects start with a still-image composition and use Brief → Visual concept → Image generation/review → Final review/export. No video pilot, motion production or external-edit prerequisite. Multiple image compositions remain possible.
- **Generator choice:** choose an image prompt profile and exact model/version when creating either project type; video projects also choose their video profile/model. Allow a custom model name. Keep choices editable later. Selecting a profile never authenticates a provider account.
- **Creative intake:** ask the important unanswered questions before choosing a setup or generating: intended vision/emotion, art style and intended use. Audience, constraints and actual references add context. A template's default style is not the creator's answer. Ask for missing generator/model information too.
- **Creator delegation:** if the creator wants recommendations, offer a small relevant set of directions. If they explicitly delegate the decision, record the delegation and the selected recommendation. Avoid repeatedly asking questions already answered.
- **Approvals:** every approval checkbox starts off for new UI, agent, batch and duplicate projects. Existing projects keep their policy. An explicitly applied saved workflow may restore its chosen policy. Automatic progression must still satisfy media validity and required quality checks, and must never be labelled human approval.
- **Production bible:** upload real image references directly to an entity, or attach existing project images. Support multiple attachments, visible thumbnails, larger previews and detachment without deleting the underlying file. Preserve entity identity/version and revision conflict handling.
- **External creations:** upload real images or videos made anywhere, identify their role and shot, and optionally record the generator and original prompt. References, shot takes and final edits are separate roles. Imported takes start unselected and need the same selection/quality checks as other takes; do not invent a generation job, spending amount or prior approval.

## Technical handover

Keep the existing FastAPI/SQLite/local-media backend, stdio MCP bridge, Next.js interface and Windows shell. Browser uploads pass through the authenticated local API; MCP imports use validated local inbox paths. No hosted media service is required.

### Project and agent interfaces

- `create_project` and `create_batch` accept `output_type: image|video` plus initial `settings`. Old projects without an output type read as video.
- Settings add `image_model`, `video_model` and `creative_intake` with text answers `vision`, `art_style`, `purpose`, `audience`, `constraints`.
- New projects carry a creative-intake requirement. `get_project.creative_intake` exposes saved answers, missing questions, instructions and editable setup suggestions. `next_action` returns `ask_creator` while essential answers/models are missing. This is an input requirement, independent of approval switches. Existing projects are not newly blocked.
- Agents save answers through `update_settings`, explain how framing/lens/lighting/palette serve the brief, then use existing production/shot controls to apply the setup. They must retain deliberate creator overrides.
- Compiled prompts, previews and exports carry the exact model, creative intent and guidance provenance. Model/profile changes invalidate the corresponding outputs even when rendered text is unchanged. Generic/custom models are explicitly unverified until the agent checks their actual documentation/capabilities.
- Existing Flow/Veo and Runway prompt families retain their differences: Runway I2V emphasizes motion using the actual appearance reference; Veo carries scene/action and audio direction; image prompts describe appearance. Do not invent model parameters or treat a known family as live capability verification.
- `import_external_take` registers validated media without requiring a generation claim; metadata identifies its external origin. Import provenance and unknown costs remain truthful. Changing a project must not overwrite original takes.
- Image progression must be enforced by backend active steps, not only hidden navigation. Image exports contain selected actual images and a portable manifest, not fictional video output.

### Files to start with

- Backend progression, creation and imports: `backend/studio/workflow.py`, with API/MCP commands and existing supporting modules.
- Creator intake and model guidance: `backend/studio/intake.py`; the shared prompt compiler remains `backend/studio/generators.py`.
- UI: existing Studio workspaces, with shared creation/intake/upload components rather than separate disconnected prototype pages.

## Verification checklist

Implementation is present on this branch. Verification: 152 backend tests, 50 interface tests and 12 desktop tests; production build with Next.js 16.4.2. Production-dependency audit reports zero known vulnerabilities. The framework was patched after the original build reported an advisory. Actual browser rendering and a new packaged-installer smoke run remain outstanding: automatic approval review rejected launching the UI server as “blocked by policy.” Component tests do not substitute for those checks.

- [x] Test project/API creation and image batch payloads with the same choices/defaults.
- [x] Test new approvals off, explicit gates and preservation of saved policy.
- [x] Test missing intake and model questions, saved answers and honest default/source distinction. Explicit delegation is documented agent behavior, not an automatic conversation service.
- [x] Test an actual validated image-file workflow with no MP4, pilot or editing prerequisite and export selected files. Fixtures prove software behavior, not artistic quality.
- [x] Test compiled prompt families/model metadata and model-only invalidation; custom guidance remains unverified.
- [x] Test multipart bible upload/binding and wrong-kind/stale-revision/canonical-identity rejection; UI components support preview/attach/detach.
- [x] Test external take import, explicit selection/inspection, prior-take preservation and unknown-cost correction without fabricated jobs.
- [x] Retain media validation/path/size checks and test image-project video rejection.
- [x] Run backend, frontend and desktop suites and production frontend build.
- [x] Test persisted actor-specific rule acknowledgements, policy/model invalidation, integer revision enforcement, actual-next-step preparation and safe return of previously claimed outputs.
- [x] Test Orchestra desktop naming while preserving existing data, credentials, overrides and installation identity; keep service/MCP compatibility identifiers unchanged.
- [ ] Inspect the real rendered image/video creation and attachment flows on desktop and mobile.
- [ ] Before shipping another installer, bump the beta version, package the tested commit and run the installed-app/MCP/media/persistence smoke checks. Keep the earlier beta artifact intact.

## Commands and remaining release work

Backend tests, from `backend`: `.venv/Scripts/python.exe -m unittest discover -s tests -q`.

Frontend, from `frontend`: `npm test` and `npm run build` using Node 22.12 or newer. Desktop, from `desktop`: `npm test`.

After implementation validation, review the diff, push the development branch and open a focused pull request. A new release/merge and a visibility change are separate actions; do not infer permission to republish publicly from the earlier public beta. Publisher signing, a second-computer installer trial, real artistic pilots and any project-wide licensing decision remain separate work.
