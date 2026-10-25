# Orchestra 0.3.1 release verification

25 October 2026, Windows 11 x64.

## Source validation

- Backend full suite: 291 tests passed in 124.517 seconds. Two additional legacy-discovery and secret-safe-diagnostic regressions were then added; the focused connection suite passed all six tests. The subsequent frozen checks exercise the final shipped runtime; no IPv6 service launch is claimed.
- Frontend: 84 tests passed; production build and TypeScript passed using Node 24.22.1.
- Desktop: 18 tests passed, including named config formats and installed paths with spaces.
- Focused independent review found no critical or important issues; real frozen-process validation remains a separate check.
- Existing frontend lint debt is unchanged; this maintenance release does not claim a clean lint run.

## Packaged validation

Built `Orchestra-Setup-0.3.1.exe` from runtime commit `923948f`. Size: 471,365,046 bytes. SHA256: `d01aef442110e690e6c6142a0dda8dc2923e7868248bfaaed545ed1c6f2b7c10`.

The actual unpacked payload passed both a fresh-data run and a restart/persistence run: clean PATH, bundled FFmpeg/FFprobe import, all 26 study URLs, 16 recipes, schema-3 claim/execution/real synthetic PNG return, single-instance handling, owned-child shutdown and retained database. Both runs hid the legacy runtime record and substituted a synthetic shadow credential before real MCP SDK initialize/list_tools/capabilities/recipe requests; 53 tools and 16 recipes were available. Records: `.superpowers/Frame desktop smoke JPgij3/verification.json` and `.superpowers/Frame desktop smoke 9ilPj0/verification.json` (local, excluded from Git).

Cross-package boundary: launched the frozen `serve` process using a temporary Windows interactive task, outside the Codex package. Health confirmed the original, unredirected Roaming root. A frozen MCP client launched from packaged Codex then initialized and authenticated successfully, exposing 53 tools and 16 recipes. The task was stopped and deleted. The initial Shell.Application launch was insufficient because it retained AppData virtualization; that was not counted as the cross-package proof.

All four copied configurations parsed successfully with Python TOML/JSON parsers. Existing user projects were not used as test fixtures. No paid media or artistic validation was performed.

## Limits

No fresh NSIS install/upgrade, signing, second physical computer, real provider generation or artistic pilot is claimed. The installer embeds the verified unpacked payload. Existing project databases and credentials are not migrated. Earlier release tags and assets remain unchanged.
