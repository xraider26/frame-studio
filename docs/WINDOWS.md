# Frame Studio for Windows

Download `Frame-Studio-Setup-0.2.0.exe` and its SHA256 file from the [Windows beta release](https://github.com/xraider26/frame-studio/releases/tag/v0.2.0-beta.1). It is unsigned. Publisher signing and testing on a second physical computer remain release work. GitHub requires repository access while the repository is private.

## Install and use

Run setup, choose the installation folder and open Frame Studio from its shortcut. Python, Node.js, FFmpeg/FFprobe, the studio interface, generated example assets and source-rule metadata are bundled. Users do not need this repository, its drive/folder layout, a terminal, or separately installed runtimes. Generation still requires their own agent/tool or configured API adapter.

The app starts its own loopback services on available ports and opens `/studio`. It can coexist with a source checkout on ports 3000/8010. The window is sandboxed; it does not load remote pages inside the studio. External HTTPS links open in the default browser.

Projects, media, keys and logs are stored separately under the current Windows user's application-data directory, normally `%APPDATA%\Frame Studio\studio_data`. The Frame Studio menu opens the actual data directory. This directory is not inside the installation folder and is retained on uninstall. Existing repository projects are not silently copied or replaced. Back up the data folder before moving to another computer; credentials remain private.

## Connect an agent

Open **Connections & MCP** and choose the client format. The configuration is generated from the actual installed service executable and that user's data directory. No developer username, drive or checkout path is hardcoded. The Frame Studio menu also offers **Copy MCP configuration** in JSON format. Add it through your agent's normal MCP settings; the app does not edit global client configuration.

Keep Frame Studio open while using MCP. Its bundled `FrameStudioService.exe mcp --data-dir <actual data directory>` discovers the current local API and verifies the running instance before using its token. Closing the app stops its owned services and removes current runtime discovery; saved projects remain.

## Build from source

Build requirements: Windows x64, Node.js >=22.12, Python 3.12, `uv`, and FFmpeg/FFprobe on the build machine. Install the source application's backend/frontend dependencies first. Runtime dependencies are separate from build-only tools.

```powershell
uv pip install --python backend/.venv/Scripts/python.exe -r desktop/requirements-build.txt
backend/.venv/Scripts/python.exe desktop/make_icon.py
Set-Location desktop
npm ci
npm test
npm run build
```

The build creates Next standalone output, freezes the Python service/MCP bridge, stages an explicit resource allowlist and builds the per-user NSIS installer plus SHA256 file. `FRAME_STUDIO_PYTHON`, `FRAME_STUDIO_FFMPEG` and `FRAME_STUDIO_FFPROBE` can select build-machine executables explicitly. Rebuilding can use `node desktop/build.cjs --skip-web` or `--skip-freeze` only when that respective build output is already current. Never use stale outputs for a release.

`desktop/build/`, `desktop/dist/` and dependencies are ignored by Git. User data, original private course PDFs, tokens and API keys are excluded from packaging. Bundled software notices are under `desktop/THIRD-PARTY-NOTICES.md` and the installed resources.

## Verified beta scope

On the current Windows 11 x64 machine, both the unpacked app and an actual silent setup installation in a different `C:` folder passed a clean-PATH check: startup, 26 example image URLs, nine production recipes, dynamic installed MCP configuration, video import using bundled FFmpeg/FFprobe, actual stdio SDK communication with 43 tools, single-instance handling, child-process shutdown and retained data files. Test media/projects were isolated fixtures. These checks do not replace testing on a separate computer or validate artistic video quality.

To rerun the binary check from the build machine: `node desktop/smoke.cjs "<path to installed Frame Studio.exe>"`. It starts the real app with isolated fixture data and no Node/Python/FFmpeg on PATH, writes reports under ignored `.superpowers/`, and exits automatically. The Python MCP SDK is needed only by this verification script, not by the installed user's agent.
