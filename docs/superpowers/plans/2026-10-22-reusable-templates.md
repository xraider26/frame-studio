# Reusable Templates Implementation Plan

> Execute inline using executing-plans; one final independent review.

**Goal:** Save successful project workflow/settings as reusable named local templates, with selectable settings, workflow gates, and story/shot-plan sections. Reuse from project creation or apply selected sections to an existing project; rename/delete saved templates.

**Architecture:** A separate SQLite template table stores sanitized immutable snapshots and revisioned metadata. Built-in formats remain available. Saved-template projects receive fresh IDs, jobs, reviews and media selections. Existing-project application is atomic with expected revision, respects running jobs, invalidates affected outputs, retains actual files, and restores no old approvals. Template data excludes credentials, media bindings, observed capabilities, cost history/budgets and experiments. Workflow-policy application remains human-only; agent-created projects keep default approval gates.

**Tech Stack:** Existing FastAPI/SQLite/Pydantic, Next.js/React, existing orange/glass styles. No new dependencies.

**UI:** Calm template library with a save form for the current project, section checkboxes, template rows showing saved sections and usage notes, actions for new project/apply/rename/delete. Existing new-project picker includes saved templates. Applying to an existing project explicitly previews chosen sections and requires a click in that panel. Reference files must be reattached. Optional creative-default source selects a successful shot’s effective camera/light/art look without copying its story.

## Review focus

- Template snapshots survive source edits/deletion and app restart.
- Selective save/application preserves unselected fields and existing files.
- Fresh shot/continuity IDs and no dangling reference/bible media IDs; no stale job reuse.
- Agents cannot change approval/QC policy through templates; stale project/template revisions fail atomically.
- Forms retain local edits under polling; API and UI errors remain recoverable.

## Tasks

- [ ] RED backend tests for snapshot persistence, selective capture, new-project identity/reset, existing-project invalidation, stale revisions and authority.
- [ ] Implement `saved_templates.py`, store table, project creation integration and API/MCP operations.
- [ ] RED React tests for saving selected sections and applying a template; implement template library and integrate saved choices into the project picker.
- [ ] Full backend/UI checks and production build; independent review and regression fixes.
- [ ] Merge locally, rebuild/restart the existing app, verify HTTP/API and record precise limits. No GitHub push or paid generation.
