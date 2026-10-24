# Templates and production navigation

These features are in the next-beta source, separate from the published `v0.2.0-beta.1` installer.

## Find the right workspace

Global navigation contains **Projects**, **Templates** and **Connections**. Within a project, follow **Brief → Plan → Create → Review → Export**. Each stage reveals its related tools. **Continue** opens the tool for the actual next required action; it does not complete the action or bypass a quality gate. Project settings remain available separately.

Plan contains the concept/script, production bible, shot direction and visual library. Video projects also have Sequences. Create contains generator handoffs and returned-media imports. Review contains takes, approvals and final checks. Export contains the image package or external-editor handoff. Unsaved brief/script/final-note drafts are retained in the current browser session when switching tools or projects; save them to persist them in the project.

## Image and video starting points

Open **Templates**, choose **Image** or **Video**, then **Built-in** or **Saved**. New-project creation uses the same media-type filter.

Image formats include portrait (4:5), product (1:1), thumbnail (16:9), poster (2:3), concept art (16:9), social creative (1:1) and custom (16:9). They have still-image composition guidance and quality checks. Their examples reuse existing illustrative studies with source attribution; they are not validated outputs for the new format. Video retains its nine content recipes and video-specific checks.

Save a successful setup with the desired creative settings, workflow policy and optional story/shot plan. Saved templates carry their output type. Story/workflow restoration must match the destination's type; settings-only transfer remains available. Older saved templates infer their type from the source project when possible and otherwise default to video. Existing legacy image projects remain readable and duplicatable.

Choose generator profiles and exact model names when creating a project. These choices tailor prompt guidance and do not connect an account. The creator's brief and explicit overrides remain authoritative.

## Video sequences

In **Plan → Sequences**, choose a pattern:

| Pattern | Planning intent |
| --- | --- |
| Creator explainer | A-roll with supporting B-roll and a clear payoff |
| Podcast conversation | Establishing coverage, speakers and reactions |
| Interview documentary | Interview audio, evidence and cutaways |
| Product demonstration | Problem, demonstration and supporting detail |
| Short drama | Story progression and reaction coverage |
| Montage | Rhythmic detail, progression and resolution |
| Hook / reveal / payoff | Curiosity followed by a clear answer |

Preview the ordered roles, allocated durations, transitions and audio continuity before applying. The allocation uses the project's runtime, splits clips longer than 30 seconds and refuses a runtime too short to give each role at least one second. Too-long plans are rejected at the 200-clip limit.

Applying replaces the shot plan and reopens script preparation. Authored work requires explicit confirmation; running generation blocks replacement. Settings and review policy remain, previous outputs become stale and spending history stays intact. **Review → Takes & quality → Earlier plan media** lets you view/download retained takes. Import a downloaded file onto a current shot if you choose to reuse it; it still needs current quality checks.

Coverage roles, purpose, transitions and source-audio links travel into generation/editor handoffs. J/L cuts and similar techniques are instructions for the external edit. Orchestra does not stitch clips or render these edits itself.

MCP exposes `sequence_catalog` and `preview_sequence` for planning. Applying a replacement sequence is a human action in the studio; an agent cannot bypass it. Agents can continue authoring through the existing revision-checked workflow tools.
