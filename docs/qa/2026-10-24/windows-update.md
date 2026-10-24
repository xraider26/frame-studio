# Orchestra 0.2.1-beta.1 Windows update

Source application revision: `f8e42a70dde3570653b0c0c053f0ab6615aebfa4`.

Installer: `Orchestra-Setup-0.2.1-beta.1.exe` (local build; no new GitHub release published).

SHA256: `22be670455a1cbf2d0aec2aaba3d37e6f105690d678a58e56404ca6703d5a9c6`.

## Verified

- 187 backend, 66 interface and 14 desktop tests pass; Next.js production build and PyInstaller freeze succeed.
- A fresh review found no actionable issues in the packaging changes or final route-cache fix.
- The unpacked app passes clean-PATH startup, 26 illustrative still URLs, 16 image/video recipes, Qwen/ComfyUI capabilities, bundled FFmpeg/FFprobe import, the real MCP bridge (48 tools), singleton behavior, shutdown and saved-project recovery.
- Existing installed database and available credentials were backed up before installation. Project media remains in its existing application-data directory.

## Upgrade regression found and fixed

The first installed-copy smoke check found a mixed version: the new backend and bundled interface files were correct, but Next.js served older generated HTML from `resources/web/.next/server/route-cache`. Hash comparison showed the differences were in generated route-cache files; the new application bundles matched the unpacked build.

Startup now clears only that fixed disposable cache directory before launching Next.js. The path is checked, symbolic-link ancestors are rejected, and tests confirm project data and application bundles are preserved. The fixed unpacked build passes the complete smoke check.

## Final installed verification

- [x] Corrected installer applied to the existing installation directory; installer exit code 0, installed build metadata matches source revision above.
- [x] Installed binary passes the complete smoke check and saved-project recovery. Reports are kept in the local ignored `.superpowers/Frame desktop smoke lCPgGd` (unpacked) and `Frame desktop smoke uhqLtZ` (installed) directories.
- [x] Existing installed project records match the pre-update database backup (both contain zero projects). Source-checkout project storage remains separate and unchanged. The backup is under the installed data directory's `.backups/before-0.2.1-beta.1-20261024-093833`.

Live Qwen/H3 inference, second-computer testing and publisher signing remain separate validation work. Earlier `v0.2.0-beta.1` tag/assets are unchanged.
