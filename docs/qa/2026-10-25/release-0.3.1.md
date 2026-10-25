# Orchestra 0.3.1 release verification

25 October 2026, Windows 11 x64.

## Source validation

- Backend full suite: 291 tests passed in 124.517 seconds. Two additional legacy-discovery and secret-safe-diagnostic regressions were then added; the focused connection suite passed all six tests. No runtime source changed after the full suite except IPv6 loopback URL formatting, exercised by the subsequent frozen verification.
- Frontend: 84 tests passed; production build and TypeScript passed using Node 24.22.1.
- Desktop: 18 tests passed, including named config formats and installed paths with spaces.
- Focused independent review found no critical or important issues; real frozen-process validation remains a separate check.
- Existing frontend lint debt is unchanged; this maintenance release does not claim a clean lint run.

## Packaged validation

Pending packaging and frozen smoke checks. The new smoke scenario hides the legacy runtime record and substitutes a synthetic shadow credential before a real MCP SDK initialize, tool listing, capabilities and recipe request. It does not generate paid media or claim artistic validation.

## Limits

No signing, second physical computer, real provider generation or artistic pilot is claimed. Existing project databases and credentials are not migrated. Earlier release tags and assets remain unchanged.
