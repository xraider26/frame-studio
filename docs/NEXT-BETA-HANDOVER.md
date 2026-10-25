# Orchestra — image projects and creator-led production

Date: 24 October 2026. Development branch: `feature/image-projects-creative-intake`.

The product is now **Orchestra**, formerly Frame Studio. The interface, desktop shell, icon and future installer name are updated; installation identity, existing storage and MCP configuration keys remain stable. The GitHub repository path is unchanged.

Additional next-beta work: mandatory per-project MCP workflow contracts with persisted actor acknowledgements, revision/workflow enforcement and policy/model invalidation; the [reviewed shared prompting guide](PROMPTING-GUIDE.md), five editable style setups and FLUX/Midjourney profiles. See [agent bootstrap and compatibility](MCP.md#strict-agent-contract-next-beta-source). Acknowledgements do not prove inspection or guarantee a model's behavior outside the app.

The latest source adds seven image formats, typed Image/Video and Built-in/Saved template filters, seven previewable video sequence patterns and five-stage project navigation. Sequence coverage/audio intent reaches handoffs; applying a plan is human-only and safely retains previous media. Retained takes are accessible under Earlier plan media. Story-only template restoration clears obsolete default audio links. See [templates and sequences](TEMPLATES-AND-SEQUENCES.md).

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

24 October update: image prompting and mapped direct ComfyUI execution are implemented; see [setup and limits](COMFYUI.md). Fresh checks passed **187 backend, 66 interface and 14 desktop tests**. **Orchestra 0.2.1-beta.1** was built and installed locally; unpacked and installed binaries pass clean-PATH startup, real MCP, bundled media tools and persistence smoke checks. An actual upgrade regression involving stale Next.js route-cache files was fixed and retested. See the [Windows update evidence](qa/2026-10-24/windows-update.md). The earlier beta tag/assets remain unchanged; no new GitHub release is published by the local update.

Implementation is present on this branch. Fresh verification: **165 backend tests, 63 interface tests and 12 desktop tests**; production build with Next.js 16.4.2. The prior production-dependency audit reported zero known vulnerabilities; dependency versions are unchanged in this update. Actual browser rendering and a new packaged-installer smoke run remain outstanding: automatic approval review rejected launching the UI server as “blocked by policy.” Component tests do not substitute for those checks.

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
- [x] Bump the beta version, package the tested application commit and run the installed-app/MCP/media/persistence smoke checks. Earlier beta artifact retained. Signing and second-computer validation remain external release work.

## Commands and remaining release work

### Next update: seamless creator decisions through chat/MCP (25 October 2026)

- [ ] Fix duplicated Project generators sections: creator screenshot of Review → Takes & quality shows the identical heading, selected generator and Change generator setup button rendered five times. Render one compact project-level generator summary; expand setup details on demand, and avoid consuming the review workspace with repeated configuration. Add a render regression asserting only one summary after navigation/state updates and check the actual page. Screenshot: `C:\Users\Reforged\AppData\Local\Temp\codex-clipboard-dd2361c0-8b06-44cd-8d8c-671872e77e65.png` (local reference only).

Creator requirement: once connected, the user should be able to direct production entirely in chat. Direct user feedback and permission must be actionable through MCP; do not send the user back into Orchestra merely to repeat a decision already made in the conversation. Apply this across equivalent app-only decision gates, not just image calibration. This is pending implementation after 0.3.1; the current installed calibration gate still requires the app decision.

- [ ] Treat an explicit modification request concerning the current image as rejection of that take for the requested revision and authorization to make those changes. Example: "No obvious walkpaths; ground-level view; for cinematic scenes" must record the feedback, preserve the original take, reopen only the affected inputs and allow a replacement without a separate Reject click or another confirmation question. This does not mean permanent deletion or acceptance of the replacement.
- [ ] Add MCP operations for creator decisions expressed in chat: calibration acceptance/rejection/revision, workflow review/approval, take selection, generator changes, and equivalent currently UI-only production controls. Audit every `human_only` restriction, `await_*` state, agent instruction and UI handoff for cases where the human has already supplied the relevant decision in chat. Budget/policy changes also need a chat path when explicitly requested by the user; requesting an image edit alone does not change unrelated limits.
- [ ] Record the exact user instruction, relevant project/shot/take and current revision, decision type, scope, originating client and timestamp. Label conversational evidence honestly as a user instruction relayed through the connected agent; do not mislabel it as a browser click or infer decisions from generated content, external documents or another agent. Distinguish rejection-for-revision, acceptance, selection and deletion.
- [ ] Resolve a clear "this image" against the current representative take. Ask once only if the target or requested action is genuinely ambiguous. Preserve reference requirements, exact submitted-request evidence, actual technical inspection, spending bounds and existing files; the implementation must accept authorized decisions rather than simply disabling all gates.
- [ ] Make decision + revision transitions atomic and idempotent, with stale-revision/asset checks and an audit trail. Refresh workflow contracts after relevant policy/model changes. Update MCP descriptions, bootstrap guidance, docs and UI status so all surfaces agree that chat is a supported creator-decision channel.
- [ ] Add end-to-end regressions for chat modification after technical review, explicit chat acceptance, take selection, other review gates, policy changes explicitly requested in chat, ambiguous/stale targets, duplicate delivery, and absence of a user instruction. Verify the full rejection → edit → generate → return → inspect loop proceeds without an app click.
- [ ] Complete the media-return boundary too: a generated file written by packaged Codex can land in its AppData overlay while the desktop's inbox is outside that overlay. Add an authenticated job-bound upload/staging path that returns the bytes to the existing claimed job while preserving owner/execution checks. Do not require manual uploads, alternate external takes or scheduled file-copy helpers. Reproduced during this same image run; the temporary one-file helper was removed after successful return.

Current reproduction: project `ed01e370afa641e38f84bbb534f96cc0` (Worlds We Found Together), take `856f5b71fd3746d4a02de86c1a630f4d`. The creator requested removal of walkpaths and a ground-level cinematic viewpoint. `revise_shot` returned `calibration_pending` despite that direct modification instruction. Prepared revision details are in `G:\AI\YT\assets\artwork\surreal-worlds\creator-revision-ground-level.md`. Preserve this work when implementing the next update; do not regenerate until the updated decision path records the creator's actual request.

### Next-update fix: installed MCP executable path (25 October 2026)

- [x] Add a target-client selector to Copy MCP config: Codex receives TOML (`[mcp_servers.frame_studio]` and its environment table); Cursor/Claude receive JSON `mcpServers`. Desktop menu also offers Antigravity. Tests preserve executable/data paths and argument boundaries; all four copied formats parse successfully.
- [x] Ensure generated/copied MCP configurations resolve the actual installed `FrameStudioService.exe` location, including an `Orchestra` installation subfolder. Existing stale commands are replaced by copying the new client-specific entry; unrelated client settings are not modified automatically.
- Observed: Codex's saved `frame_studio` command pointed to `G:\AI\Frame Studio\resources\backend\FrameStudioService.exe`; the executable exists at `G:\AI\Frame Studio\Orchestra\resources\backend\FrameStudioService.exe`. The connected MCP tool returned `[Errno 2] No such file or directory`.
- Local workaround already applied: backed up the Codex config and corrected only its executable path. The current connected tool still returned the launch error afterward; reconnection/restart and successful capabilities access remain unverified. An earlier call also reported `Studio connection token required`; do not assume correcting the path resolves authentication.
- Completed in 0.3.1: installed resources paths/config formats pass tests, and real frozen stdio initialize/list_tools/capabilities pass with 53 tools. See [release verification](qa/2026-10-25/release-0.3.1.md). The earlier error/workaround above is retained as reproduction history.

### Confirmed MCP startup blocker after Codex restart (25 October 2026)

- [x] Fix discovery when Orchestra runs outside the packaged Codex environment and the MCP child runs inside it. A separate per-launch agent-only connection under the user's home directory avoids AppData overlays; existing databases and original credentials stay in place. Real unpackaged service / packaged MCP verification passed.
- `codex mcp get frame_studio` confirms the corrected server is enabled. Codex startup logs at 06:15:31 UTC show the frozen bridge redirecting the requested Roaming data root to `C:\Users\Reforged\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Roaming\Frame Studio\studio_data`, then exiting with `backend_unavailable` and a closed MCP initialize handshake. A direct MCP SDK probe reproduced the same failure.
- The actual desktop is running from the corrected executable with the original Roaming data root. Its `desktop-runtime.json` identifies a live service; `/health` returned HTTP 200 with matching root/PID/instance. The redirected root has no `desktop-runtime.json`. Investigate `resolve_writable_root` selecting the newly created probe's redirected location before `load_desktop_runtime` discovers the already-running desktop. Current behavior hides the working desktop and gives a misleading instruction to open it.
- Additional diagnostic: read-only capabilities requests to that live service using the agent credential visible from each root both returned HTTP 401; the two credential values visible inside Codex match. Credential access across the virtualized/non-virtualized processes remains unresolved. Health success does not establish authenticated MCP access; do not claim the connection is repaired or assume changing only runtime discovery suffices.
- Regression required: launch the desktop outside Codex, launch the frozen MCP bridge inside packaged Codex, and verify initialize/list_tools/capabilities against that same desktop and existing projects. Prior tests launching both processes under the same parent do not cover this case. Also report the attempted discovery root and a useful connection diagnostic without exposing credentials.
- Resolution evidence: 0.3.1 passed that boundary using a temporary Windows interactive task outside the Codex package and a frozen MCP subprocess inside Codex. It also passed missing-runtime/shadow-credential smoke checks and restart persistence. The temporary task was removed; live project databases were not touched. Earlier 401/unresolved statements above describe the old installed build, not the verified 0.3.1 payload.

Backend tests, from `backend`: `.venv/Scripts/python.exe -m unittest discover -s tests -q`.

Frontend, from `frontend`: `npm test` and `npm run build` using Node 22.12 or newer. Desktop, from `desktop`: `npm test`.

After implementation validation, review the diff, push the development branch and open a focused pull request. A new release/merge and a visibility change are separate actions; do not infer permission to republish publicly from the earlier public beta. Publisher signing, a second-computer installer trial, real artistic pilots and any project-wide licensing decision remain separate work.

Source workflow update: project generator intake, creator-only calibration and exact execution/rule evidence are implemented. New compact transport defaults to schema3 with top-level handoff; summary polling and targeted versioned context avoid duplicate full payloads. See MCP.md and backend/benchmark_handoffs.py. Source checks do not establish installed-app or real video-generation validation.

### Credit discipline for further work

Resume from the saved progress ledger and existing uncommitted changes. Default to one direct implementation owner; add agents only for a distinct task that justifies its context cost. Pass file paths and a narrow brief rather than repeated history or entire catalogs. Run focused regressions while editing, then aggregate checks at delivery; repeat broad checks only for an actual change, failure or unresolved risk. Read logs in bounded slices and keep large assertion diffs out of tool output. Use compact claim/summary polling and fetch full context only when needed. Record completed work and validation immediately so interrupted sessions do not restart it. Report actual byte/token measurements separately; do not promise a billing reduction from a byte benchmark.


### Implemented in 0.3.2 (26 October 2026)

The chat-decision, modification-as-revision, job-bound media upload, reference staging/digest and duplicated generator-panel backlog above is implemented. Chat decisions preserve the exact relayed user instruction and commit atomically with receipts; UI actions are still available. Generator editing uses a single compact summary and preserves drafts when collapsed.

Calibration diagnosis: scene lighting/art differences were treated as independent styles; non-rendered creative-intake metadata also invalidated selected media. Both are fixed. Real shared prompt changes (including negative prompts) still invalidate affected output. Restoring the exact previously approved inputs/take now recovers that recorded approval unless a later rejection or explicit policy change supersedes it. See the 0.3.2 release notes and verification for shipped evidence and limits. Live artwork was not used as a test fixture.
