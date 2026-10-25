# Orchestra 0.3.0-beta.1 release verification

Verified on the current Windows 11 x64 machine, 25 October 2026. The test uses isolated temporary application data and Electron state; it does not replace the user's installed application, modify live projects, or call a paid generator.

## Source checks

- Backend: 287 tests passed, including the public-API calibration/rejection/repair/acceptance sequence and atomic job/context rollback.
- Frontend: 84 tests passed; final page/evidence checks passed 3/3. Fresh production build passed with locally installed dependencies.
- Desktop: 17 tests passed, including isolation of smoke-test Electron state from the installed application's single-instance lock.
- Lint: 11 existing source errors and 24 warnings remain disclosed. Generated test output is excluded; CommonJS tests use their proper import convention. Source lint rules are retained.

## Windows build

Built using Node 24.22.1, Python 3.12, PyInstaller 6.22.0 and Electron 45.0.0. The installer is unsigned. Its embedded build-info identifies runtime source commit `666d15b23accd34e113bf60413a4c4bf061f3027`. The final release commit adds only download documentation and this verification record; runtime sources are unchanged.

Artifact: `Orchestra-Setup-0.3.0-beta.1.exe`, 471,359,889 bytes.

SHA256: `d8ec5e54e31671d6b415b4a94257240eb95b25af05aaa370194688fe63b637de`.

## Packaged payload checks

Ran `desktop/smoke.cjs` against the newly built `desktop/dist/win-unpacked/Orchestra.exe` twice: first with a fresh temporary AppData directory and `--new-data`, then with the same directory to verify restart persistence. Both runs passed:

1. Startup with Node/Python/FFmpeg removed from PATH.
2. Correct bundled MCP executable and physical data root.
3. All 26 generated cinematography-study URLs available.
4. All 16 image/video recipes, including seven image recipes.
5. Qwen/ComfyUI capability declarations present, without claiming remote provider availability.
6. Synthetic MP4 reference validated with bundled FFmpeg/FFprobe.
7. Compact schema-3 image claim, owner-bound execution recording and real synthetic PNG return; next action remains technical inspection, with no creator style acceptance invented.
8. Actual frozen-service stdio MCP SDK connection: 53 tools and 16 recipes, including setup, execution recorder and targeted context tools.
9. Second launch respects the same instance rather than starting extra services.
10. Desktop-owned child processes terminate and its runtime record is removed on exit.
11. Project database persists and the saved fixture project reopens after restart.

Both runs encountered a real logical-versus-physical AppData redirect under the packaged Codex parent. The published MCP root and returned media used the physical root successfully. Temporary fixture data and logs remain outside the release assets.

## Limits

The unpacked payload used by the installer is verified; a fresh NSIS installation/upgrade, an Explorer-shortcut launch outside the packaged parent, signing and a second physical computer are not claimed. No new artistic calibration image, real ComfyUI provider, Gemini Omni/video pipeline, motion, continuity or sound validation was performed. The stopped creator trial remains stopped. Original PDFs, user data and credentials are excluded from staging and public delivery.
