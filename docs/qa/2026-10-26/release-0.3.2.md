# Orchestra 0.3.2 release verification

26 October 2026, Windows 11 x64.

## Source validation

- Backend: all 310 tests passed in 142.290 seconds, including calibration persistence, chat authority/atomicity/idempotence, reference digest checks, uploaded output and concurrent connection validation.
- Frontend: all 86 tests passed, including duplicate generator-panel navigation/refresh and collapsed editor draft retention. Production build and TypeScript passed with Node 24.
- Desktop: all 18 tests passed.
- Independent backend and frontend review findings were addressed; targeted regressions cover the corrected transaction, target-scope and concurrency issues.
- Existing frontend lint debt is unchanged; no clean lint run is claimed.

## Packaged validation

Built `Orchestra-Setup-0.3.2.exe` from runtime commit `ff876c55c14eb9fc4c16dd787d0075a588ae2b83`. Size: 471,389,999 bytes. SHA256: `e99d5cf955c0eb1d8f0651139c71d7b476a369f0a20d06f4f28a54960bf7287c`.

The actual unpacked payload passed fresh-data and restart/persistence runs: clean PATH, bundled FFmpeg/FFprobe import, 26 study URLs, 16 recipes, schema-3 execution/PNG return, single-instance handling, owned-child shutdown and retained database. Both runs hid the legacy runtime record and substituted a synthetic shadow credential before the frozen MCP SDK check. All 54 tools were available. Local records: `.superpowers/Frame desktop smoke ymkGbZ/verification.json` and `.superpowers/Frame desktop smoke pmT10N/verification.json` (excluded from Git).

The extended frozen MCP check used controlled synthetic image bytes and verified chat approval/retry, revision rejection, owned-job byte upload/retry, local reference staging and SHA256 execution matching, and a second scene retaining shared calibration. These are software fixtures, not artistic approvals or model-generation claims. The first boundary attempt exposed a test-helper argument-name collision; the helper was corrected before the successful runs.

Cross-package proof: the frozen service ran from a temporary Windows interactive task outside Codex. Health confirmed the original unvirtualized Roaming data root. A frozen MCP subprocess launched inside packaged Codex then passed all extended assertions against that same service. The temporary task and shared connection record were removed. Live user projects were not touched.

## Limits

No fresh NSIS install/upgrade, signing, second physical computer, real provider generation or artistic pilot is claimed. Existing live artwork was not used as a fixture. Older release tags/assets and project data remain in place.
