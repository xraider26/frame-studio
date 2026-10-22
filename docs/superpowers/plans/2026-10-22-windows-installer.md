# Windows installer implementation plan

> Execute with focused agents for backend/runtime and desktop shell; root owns reproducible packaging and installed-binary verification.

**Goal:** Ship a Windows x64 setup executable that installs Frame Studio with its web UI, Python backend, MCP bridge, Node runtime and media utilities.

**Architecture:** Electron hosts the existing loopback Next standalone UI in a sandboxed window. The desktop process starts its own frozen backend and Next child on free loopback ports, verifies backend launch identity, and persists only runtime discovery under a separate per-user data directory. The bundled service executable also runs stdio MCP using discovery for the running installed app.

**Tech stack:** Electron, electron-builder NSIS, Next standalone, PyInstaller onedir Python, bundled FFmpeg/FFprobe.

## Constraints / review focus

- Explicit resource allowlist: no existing projects, media, credentials, API keys, private source PDFs, dev dependencies or user machine paths in the installed payload.
- Per-user install; no admin requirement, external publish, global agent config editing, paid generation or automatic repository-data migration.
- Existing dev processes/data remain intact. Desktop owns and closes only its child processes.
- Writable data/logs remain outside installation files and survive upgrades/uninstall by default.
- Renderer node integration off, context isolation/sandbox on, local-only service listeners; external links open in browser with a scheme allowlist.
- Handle startup failures, occupied ports, wrong backend identity, duplicate app launches, shutdown, stale MCP discovery and paths containing spaces.
- No signing certificate available: label the artifact as unsigned local beta; do not promise Windows publisher reputation or cross-machine certification.

## Tasks

- [x] Backend TDD: frozen/development resource paths, per-user data, runtime discovery validation and live instance verification; implement service serve/MCP entrypoint.
- [x] Desktop TDD: child argument/environment paths, isolated ports, identity checks, safe navigation and lifecycle; implement secure shell and setup menus.
- [x] Packaging: pin build dependencies, build Next standalone, freeze backend, stage explicit resources/media utilities/notices, create NSIS setup and SHA256 manifest.
- [x] Run software tests/build; launch unpacked and installed binaries with isolated test data and clean PATH; verify real API/assets, MCP stdio and media probe; test graceful exit and persistence.
- [x] Review/fix actionable defects, document install/build/data/MCP/limitations; commit source locally and deliver installer artifact without publishing.

## Verification record
119backend tests,42frontend tests,10desktop/build tests pass. Next standalone and PyInstaller/NSIS builds succeeded. Independent review found no actionable defects. Both unpacked and actual installed app in an unrelated C: folder passed clean-PATH checks,26assets,9recipes,bundled video import,SDK stdio43tools,single-instance,childshutdown,data retained. User spotted old hardcoded MCP setup while packaging; dynamiccapabilities/JSON/TOML nowtested and livepage updated. No GitHub release or push authorized; unsigned beta remainslocal.
