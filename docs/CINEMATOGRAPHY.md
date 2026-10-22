# Visual cinematography library

Open **Camera & visual library** in the studio sidebar, or the examples link in **Shots & direction**. Browsing is available before opening a project. The existing (?) controls in the shot inspector share the same images and movement demonstrations.

The library contains 26 individual generated stills: four camera looks, five lens/depth studies, seven framing/angle studies and ten lighting studies. They use one pottery-workshop reference scene. The manifest in `frontend/public/cinematography/manifest.json` preserves exact prompts, captions, tool provenance and comparison grouping. All assets were generated with the built-in image tool and inspected; captions describe important variations rather than asserting identical pose, geometry or calibrated focal lengths. They are approximate visual examples, not footage captured on specific cameras or proof of generator performance.

Choose a category, select a technique and use **Compare looks** to view another technique from the same category and reference group. Read its use, tradeoff and original-course principle citations. The camera category describes image treatments; an anamorphic look is an optical treatment and a phone look combines several visual cues. It does not select physical equipment in an AI generator.

Eight camera movement studies use a projected spatial scene with foreground, subject and background: locked, dolly in/out, lateral tracking, pan, tilt, orbit and handheld. Each has explicit playback, manual scrubbing, camera/subject position readouts and a top-view path. Translation produces depth-dependent parallax; pan and tilt rotate the camera at a fixed position. They are labelled spatial demonstrations. No autoplay, generated-video sample or calibrated lens simulation is claimed. Reduced-motion preferences disable playback and keep manual scrubbing.

## Apply and reuse a decision

Open a project, select the target shot explicitly and inspect the changed fields before clicking **Apply to shot**. It merges only the selected technique's fields into that shot, preserving the other shot records and unrelated direction. **Apply as project defaults** merges into shared defaults and preserves existing per-shot overrides. Existing explicit shot values continue to take precedence; a blank shot field inherits the default. Browsing and comparison never save a change.

Writes use the displayed project revision. Failed or conflicting saves keep the selected technique for retry; a project change resets the selected target. Saving camera/light decisions uses the same project data already read by prompt compilation, agent handoffs and exports. This makes the intended direction repeatable, without promising identical model output.

Use the existing saved-template controls to retain a successful combination: save creative settings, and optionally use a successful shot as the look source. Save story as well when its shot plan matters. The current feature does not clear shot overrides automatically, attach these teaching images as generation references, change approval policy, contact a generator, or spend generation credits.

## Verification

Backend tests verify source scope, detached catalogue responses, safe existing asset paths, real shipped PNGs and all movement metadata. React DOM tests cover comparison without writes, explicit shot/default payloads, revision failures, project switches, reduced motion and duplicate-submit prevention. Full browser checks inspect the rendered library, comparisons, movement playback and narrow layouts. These checks establish software behavior, not artistic reliability of future productions.
