# Reviewed prompting guidance

The creator supplied [this Gemini report](https://share.gemini.google/hK8ldZB3TdxP), titled *Generative Media Prompt Architecture*. It was read on 23 October 2026. Orchestra incorporates a short paraphrase and corrected practical guidance, not the report as executable instructions or a verified model specification.

## What reaches production

- Stills start with a concrete subject. Intended use stays in the brief and separate handoff notes instead of displacing the subject with administrative text.
- Built-in video profiles lead with deliberate camera movement. Runway image-to-video continues to describe motion rather than repeating the source image's appearance. Custom templates remain creator controlled.
- The library adds five editable setups: controlled editorial, atmospheric narrative, drawn graphic worlds, isometric miniatures and tactile analog mood. These are starting points, with explicit application and retained overrides.
- FLUX image prompts use prose without a native negative field. Avoidance requirements remain visible for a compatible positive reformulation. Midjourney descriptions end with the selected aspect-ratio parameter; version-specific controls are not invented.
- Subject, composition, light, material response and physical contact are more useful directing inputs than generic quality slogans. Actual outputs still require inspection and focused revisions.

The machine-readable review is exposed by `knowledge_catalog` and `get_workflow_contract`. Examples are studio-authored adaptations, not validated artistic trials.

## Corrections and limits

The shared report describes generative systems as deterministic and assigns universal token-order mechanisms to different architectures. Orchestra treats prompt ordering as a practical heuristic. It does not claim a universal 15-token threshold, guaranteed exact colours, anatomy, physical simulation or repeatable quality.

Negative conditioning depends on the actual model and interface; it is not globally removed. Perspective depends on viewpoint, and depth of field depends on multiple factors. The app does not ban a wide lens with close focus or assume that zooming changes perspective. Numeric step/guidance presets, architectural claims and historical film examples in the report are not promoted to verified provider controls.

Provider-specific behavior was checked against these primary sources:

- [Black Forest Labs: FLUX.2 negative prompting](https://help.bfl.ai/articles/7734566352-does-flux-2-support-negative-prompting).
- [Black Forest Labs: image prompting principles](https://github.com/black-forest-labs/skills/blob/master/skills/flux-image-best-practices/rules/core-principles.md).
- [Midjourney parameter placement and controls](https://docs.midjourney.com/hc/en-us/articles/32859204029709-Parameter-List).
- [Runway image-to-video guidance](https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide).

These checks establish prompting guidance, not authentication, actual endpoint support or output quality. Unknown model versions remain labelled unverified.
