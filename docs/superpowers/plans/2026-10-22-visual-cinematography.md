# Visual cinematography library implementation plan

> Execute the approved design in the existing studio with TDD and focused agents.

**Goal:** Help a creator see, compare, choose and reuse camera, lens, angle, movement and lighting directions that serve their vision.

**Architecture:** Enrich the existing knowledge catalogue with local generated still examples and verified principle citations. Replace the reference list with an image-led comparison workspace, share its media with inline (?) help and use existing revision-checked shot/default update operations. Movement previews are explicitly procedural spatial demonstrations; they are not generated video samples or model capability evidence.

**Tech stack:** Existing Next/React, SVG perspective projection, FastAPI/Python, built-in image generation. No new runtime dependencies.

**Visual thesis:** Calm dark glass and orange controls, with a large comparable image as the main decision surface.

**Content plan:** Category navigation; sample and comparison; purpose/tradeoff/source detail; explicit target and changed-field preview before applying. Saved templates remain the reusable look mechanism.

**Interaction thesis:** Deliberate A/B comparison, playable/scrubbable camera paths and explicit application without changing values while browsing. Respect reduced motion and keyboard navigation.

## Constraints and review focus

- User approved implementation; retain existing data and selected shot overrides, do not spend on video generation or alter provider connections.
- Same reference scene for still variations, with captions explaining changed setup; approximate illustrations are not calibrated optical tests or identity guarantees.
- Camera look is distinct from angle/lens/light. Anamorphic is an optical treatment, not a camera body; camera labels do not select physical hardware in AI generation.
- No automatic mutation on selection/comparison; use current revision and existing draft conflict handling.
- Applying project defaults leaves per-shot overrides effective; explicitly show scope and changed fields.
- Missing sample files must fall back honestly rather than fabricate images; asset paths stay inside the public cinematography directory.
- Movement projections show camera translation versus rotation and parallax; no photo pan is presented as a dolly.

## Tasks

- [x] Backend: RED tests for sample presence/path safety, citation scope, isolation and movement coverage; enrich catalogue; targeted tests GREEN.
- [x] Assets: Generate and inspect 26 individual still examples across camera/lens/framing/lighting; store exact prompts and comparison metadata in public/cinematography/manifest.json.
- [x] Frontend: RED interaction tests for comparison/no-mutation/explicit apply/revision handling; implement library, inline samples, playable spatial movement previews; test GREEN.
- [x] Integrate navigation/current shot context, document scope, run full suites/build and focused review; correct actionable findings.
- [x] Restart intended local services, verify actual browser UI and asset URLs, save screenshot, commit locally.

## Verification record
Backend105tests pass; frontend39tests pass; production build and targeted eslint pass. Independent review found no actionable defects. Live browser: no-project library isolation, camera category first, side-by-side examples, movement scrubbing/playback, phone-width overflow375/375, inline camera-look generated help, no console errors. HTTP checks:26images,8movement records,10sources. All26stills inspected; two first drafts replaced after visual review. No real user project mutated in browser testing. Local rollout complete; no push requested.
