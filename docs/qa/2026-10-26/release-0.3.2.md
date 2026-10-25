# Orchestra 0.3.2 release verification

26 October 2026, Windows 11 x64.

## Source validation

- Backend: all 310 tests passed in 142.290 seconds, including calibration persistence, chat authority/atomicity/idempotence, reference digest checks, uploaded output and concurrent connection validation.
- Frontend: all 86 tests passed, including duplicate generator-panel navigation/refresh and collapsed editor draft retention. Production build and TypeScript passed with Node 24.
- Desktop: all 18 tests passed.
- Independent backend and frontend review findings were addressed; targeted regressions cover the corrected transaction, target-scope and concurrency issues.
- Existing frontend lint debt is unchanged; no clean lint run is claimed.

## Packaged validation

Pending final installer checks; release publication follows verification.

## Limits

No fresh NSIS install/upgrade, signing, second physical computer, real provider generation or artistic pilot is claimed. Existing live artwork was not used as a fixture. Older release tags/assets and project data remain in place.
