# Contributing to Frame Studio

Frame Studio is an early beta. Small reproducible bug reports, installation feedback and real workflow observations are useful. Describe the creator's task and expected result before proposing a large implementation change.

The project-wide license has not been selected yet. Do not assume public repository visibility grants a reuse license; licensing should be settled before substantial outside code contributions. Bundled third-party components retain their own notices.

## Choose the right source

The Windows beta is tagged `v0.2.0-beta.1` and its implementation is merged into `main` through [PR #1](https://github.com/xraider26/frame-studio/pull/1). Start new development branches from `main`; use the release tag to reproduce the shipped beta. Repository documentation and subsequent development may be ahead of the released installer.

For a reproducible beta checkout, follow the [root README](README.md#develop-from-source). Use Node.js 22.12+, Python 3.12 and the existing lockfiles/requirements. Keep runtime data, test outputs and dependencies out of Git.

## Verify the layer you changed

From `backend`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -q
```

From `frontend`:

```powershell
npm test
npm run build
```

From `desktop`, after `npm ci`:

```powershell
npm test
```

Installer changes need an actual built-binary check, not just source tests. See [Windows build and verification](docs/WINDOWS.md). Documentation-only changes should check relative links, referenced assets, examples and claims; they do not need another media-generation run.

## Preserve these boundaries

- Browser human approval and agent-recorded evidence are different authorities.
- Browsing examples must not mutate project settings. Writes use current revisions; local drafts need explicit conflict recovery.
- Preserve user overrides, selected takes and unrelated project records when changing direction.
- Return real media and truthful costs. Synthetic test fixtures and generated teaching examples must remain labelled.
- Keep prompt compilation, MCP handoffs and exports consistent. A prompt profile is not an account connection or a verified vendor capability.
- Bind services to loopback, keep tokens out of browser responses and packages, and avoid silent paid-job retries.
- Keep data outside installation files. An upgrade or uninstall must not silently remove user projects.

## Report a problem

Open an [issue](https://github.com/xraider26/frame-studio/issues/new) with the version/commit, execution mode, reproduction steps and expected/actual outcome. Prefer a minimal synthetic project. Do not attach real credentials, private project databases, original paid course PDFs or media without permission. Use [private reporting guidance](SECURITY.md) for sensitive issues.
