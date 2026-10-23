# Templates and coherent production workspaces

> **For agentic workers:** Use the existing subagent implementation split or execute these tasks sequentially. Checkboxes record implementation and verification, not product approval.

**Goal:** Make image/video starting templates, reusable filming sequences and the next required action easy to find in Orchestra.

**Architecture:** Keep the existing project store, strict MCP contract and generation pipeline. Typed catalogues and sequence plans feed the same prompt compiler, quality gates and exports; a stage navigation layer organizes the existing tools without changing their authority.

**Visual thesis:** Restrained orange accents on dark glass, clear typography, open working space and one primary action.

**Content plan:** Global Projects/Templates/Connections; project Brief → Plan → Create → Review → Export, with small task-specific subnavigation. Template browsing separates media type and saved/built-in sources.

**Interaction thesis:** Preserve drafts across tool changes, show current task/continue routing, and preview/confirm destructive plan replacement. Use small active-state transitions; respect reduced motion.

## Tasks

- [x] Backend: seven dedicated image recipes, media-type metadata and saved-template compatibility; retain legacy image projects without rewriting their creative settings.
- [x] Backend: seven editable creator/filmmaking sequence patterns, coverage/audio intent, safe preview and atomic human application; expose planning context in MCP and editor/generator handoffs.
- [x] Frontend: unified Image/Video template hub and saved setups; remove stacked duplicate template workspaces and video-only language in image details.
- [x] Frontend: sequence browser with ordered roles, explanations, actual allocation preview and explicit confirmation before replacing work.
- [x] Frontend: five-stage project navigation with relevant subtools and a current-task action; preserve tools and drafts; responsive navigation CSS implemented.
- [x] Verify backend (165), UI (63), desktop (12) and production build. Current published installer unchanged.
- [ ] Inspect actual desktop/mobile browser rendering. UI-server launch rejected by automatic approval review as “blocked by policy”; manual startup requested. Responsive layout is not visually verified.

## Review follow-through

Two review findings fixed with red/green regression coverage: story-only restore now clears obsolete inherited audio-source links, and takes retained after plan replacement have a view/download selector. No new generated template illustrations or artistic output certification is claimed.

## Acceptance checks

Image templates contain image-specific references, creative setup and quality checks. Creating from the hub carries the chosen type/model into real projects. Saved image and video templates remain distinguishable and cannot replace the wrong media type's story/workflow.

Sequence patterns explain A-roll/B-roll, podcast/interview coverage, product demonstrations, drama, montage and hook/payoff structures. Coverage roles, source audio links and editing intent survive the actual handoffs; J/L cuts are edit instructions, not an internal renderer. Existing files and review policy survive pattern application; stale revisions and agent bypasses fail.

Navigation has one selected stage/tool, routes actual next actions correctly, keeps advanced controls reachable and preserves unsaved documents rather than silently discarding them. No new generation costs, cloud dependencies or guaranteed artistic results are implied.
