# Creative production coverage

This upgrade extends the connected `/studio` application, its existing API and MCP server. It does not create another preview-only app. No live generation account or paid provider has been connected by this change.

| Requirement | Delivered surface and behaviour | Evidence / limits |
| --- | --- | --- |
| Camera, lens, composition and movement | Shot Camera inspector; project advanced defaults; custom inputs and technique patches | Effective-direction/compiler tests ensure overrides replace shared defaults. Camera/body/optics descriptions and visuals are artistic cues, not calibrated simulations. |
| Lighting and art direction | Physical source, camera-relative direction, softness, shadow depth, colour, practicals, materials, palette and style | Saved structured data travels through prompts, MCP and exports. World-light mismatch is a planning warning, not a physically solved lighting model. |
| (?) visual help | Hover/focus preview, click/tap pin, example selector, apply-to-draft, use/risk/source notes, Escape/outside dismissal | React DOM tests exercise real component events and narrow-viewport positioning. SVG scene illustrations show intent; no brand-specific camera test photography is claimed. |
| Story and timing | Brief/promise/payoff, hook alternatives, independent framework, timed beats, measured speech, captions and fact/source notes | Runtime and measured dialogue validation. Timing redistribution changes beat allocation, not the actual performance. No internal LLM is supplied. |
| Format templates | AI film, drama, UGC, advertisement, explainer, podcast, 2D, claymation and custom with distinct guidance; selected formats seed relevant direction | Editable starting structure and rules; not ready-made finished scripts or guaranteed outcomes. |
| Production bible | Stable character/location/prop/style IDs, versions, identity, wardrobe, voice, layout, world lights, materials and actual imported image links | Reference bindings validate IDs/asset versions/slots. Duplication remaps canonical reference IDs and continuation shot IDs. |
| Continuity | Scene IDs, opening/action/ending, timed actions, before/after state, visible entities/headcount, speaker and continuation links | State/light mismatches warn; impossible timings and unresolved inputs block handoffs. General semantic contradictions still require the agent/human's judgment. |
| Generator handoff | One compiler for preview, claimed job and ZIP; effective controls and actual reference slots and portable per-shot file mappings (including unselected bound takes), audio notes, criteria and prior-take revision context | Existing Flow/Runway/custom profiles retained. Model capability observations are user/agent supplied; vendor APIs remain the existing JSON adapter contract. A profile is not an account connection. |
| Motion sources | Import a validated MP4, bind it with the motion role and pose/framing compatibility notes; the target image stays separate | Stills cannot pass as motion video. Actual model support must be recorded/verified; no retargeting engine is supplied. |
| QC and takes | Real media preview/comparison, selected compatible take, named defect/revision, inspection evidence and optional required checks | Recorded by actor; agent evidence cannot masquerade as human approval. No automatic visual/anatomy/lip-sync scoring is claimed. |
| Targeted revision | Reopens affected shot/media and linked dependencies; retains unrelated selected takes and all files | Behaviour tests cover unchanged keyframes, unrelated images, stale returns and incompatible selections. Conservative stage-level human review may reopen. |
| Frame continuation | Real near-final PNG extraction from a returned video using local FFmpeg | Frame is registered for explicit inspection/binding; no automatic continuity or model compliance claim. |
| Image refinement | External original/mask/defect/preservation repair brief; revision handoff retains prior-take context | Actual editing is performed by the user's connected agent/tool. No built-in inpainting model or upscaler is added. |
| Resources | One project unit, total/pilot limits, planned costs/evidence, per-shot/media-kind attempt limit, atomic claims and actual cost reports/history | Unknown prior costs can block a hard budget. Reservations are conservative; canceling locally does not prove a provider refund. External spending outside the studio cannot be policed. |
| Learning | Known/unknown costs, attempts, selected-shot cost, completed-job time, defects; sourced manual experiment/CTR/completion records | No analytics-account integration or automatic provider-balance sync. |
| External editing | Source in/out and timeline ranges, actual selected MP4s, sound/dialogue/captions/transition directions; editor JSON/CSV ZIP | Not a native NLE project or a rendered video. Missing files/short source ranges are reported. Editing and publishing remain external. |
| Existing projects and drafts | Read-time defaults, one pre-upgrade SQLite backup, stable IDs, legacy nested omissions preserved, user-only policy, revision conflicts | Tests include restart/legacy look preservation and backup closure on Windows. Structured drafts survive polling and page remounts in browser session storage when available; rebase is explicit. |

## Course material coverage

The accessible source is the supplied `AI_Video_Course_Review_and_Workflow.md` review/playbook. The library distinguishes adapted playbook principles from studio-authored practical examples. It supplies source/section/provenance/use/risk/apply data to both the UI and MCP. Entry counts are returned by `knowledge_catalog`, rather than treated as the original course's catalogue counts.

Original PDFs were subsequently recovered from the authenticated course classroom. Selected pages now ground the versioned production recipes, with source hashes, page citations, paraphrased directing principles, named frameworks and explicit studio corrections. See [source verification scope](COURSE-SOURCES.md) and the machine-readable [ledger](sources/verified-course-lessons.json). This is selected-page verification, not certification that all 45 originals or every technique catalogue has been imported. Lesson videos and current provider capabilities remain outside that verification.

The Template library adds nine production recipes and 27 individually generated illustrative stills. Each recipe carries reference preparation, timed shot roles, purpose-based camera/light suggestions, workflow guidance, shot-specific acceptance criteria and repair directions into MCP and exports. Basic and Professional views use the same recipe contract. New projects use the recipe; existing projects require explicit activation that preserves their settings and approval policy. See [recipe workflow and validation](COURSE-RECIPES.md).

## Verification and remaining validation

Run backend behaviour, API and SDK transport checks with:

```powershell
cd backend
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Run React DOM interactions/draft tests and the production build with:

```powershell
cd frontend
npm test
npm run build
```

SDK transport tests use actual stdio MCP and the actual FastAPI command handlers through an in-process TestClient. Media fixtures are explicitly synthetic, including the FFmpeg clip/frame extraction test. They prove software/data flow, not artistic quality or live vendor integration.

React/JSDOM tests cover option help, shot-inspector save payloads, template browsing, illustration inspection and recipe activation. Local browser checks complement these tests; they do not validate generated video quality.

No paid artistic pilot has been generated or reviewed. Production-quality claims require a real representative pilot, actual authorized generation tools/settings/budget and inspection of the full output against its criteria.
