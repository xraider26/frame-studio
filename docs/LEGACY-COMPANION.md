# Historical Flow companion prototype

This is the earlier project README, preserved for development history. Its hardware, model, credit and integration claims are historical and are not the current Frame Studio setup guide. Use the repository README and Windows guide for the released studio.

# Flow Companion Studio

## Frame Studio — connected MCP workflow

Windows desktop packaging is available through the [installer build and usage guide](WINDOWS.md). The installer bundles the studio runtimes and generates MCP setup from the actual installation and user-data paths.

The new content workflow is available at **http://127.0.0.1:3000/studio**. Start it with `./launch-studio.ps1`; see [MCP setup and workflow](MCP.md). It supports shared saved projects, agent generation handoff/return, per-step human/automatic review, generator-specific ZIP exports, API adapter connections, duplication and recoverable Trash. The legacy companion dashboard below is preserved at `/` and uses its separate API on port 8000.

Generation requires an actual local/agent tool or a configured JSON Job API adapter. Frame does not automatically access a Flow account. The old port-52741 prototype is separate from this connected app.

The creative production workspace adds per-shot camera/lighting/art direction, visual (?) option guides, story timing, production bibles, reference/state continuity, recorded quality checks, take comparison, targeted revisions and resource limits. The same records feed MCP and generator exports. The editor ZIP carries chosen clips and JSON/CSV timing. See [creative feature/source coverage](CREATIVE-COVERAGE.md) for what is implemented and what remains externally validated.

Template library now includes nine [production recipes](COURSE-RECIPES.md), three generated illustration images per format, verified course-page citations, shot-role quality checks and human finished-video assessments. Recipes guide connected agents and exports; consistent artistic quality still requires real production trials.

The [visual cinematography library](CINEMATOGRAPHY.md) adds 26 comparable generated camera/lens/framing/lighting studies, eight interactive spatial camera movements, side-by-side inspection and explicit application to shots or project defaults. The same samples appear in shot-control (?) help.

### Set up a fresh checkout (Windows)

Requires Node.js/npm, Python 3.12 managed by `uv`, and FFmpeg/FFprobe on PATH for video imports.

```powershell
uv venv backend/.venv --python 3.12
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-studio.txt
Set-Location frontend
npm ci
npm run build
Set-Location ..
./launch-studio.ps1
```

Open **http://127.0.0.1:3000/studio**. For tests, run `.venv/Scripts/python.exe -m unittest discover -s tests -v` from `backend`. The legacy dashboard also requires its optional services and dependencies; use the connected `/studio` route for the MCP workflow.

Runtime projects, media, databases, API keys, credentials, dependencies and test outputs are excluded from Git. The app creates its local `studio_data` folder on first start. MCP configuration examples use the current machine's paths; adjust them to your checkout before adding the server to another client.

> **Hardware-Tuned Director's Companion for Google Flow, ComfyUI, and FFmpeg**
> Tuned specifically for **AMD Radeon RX 9070 XT (16GB VRAM)** + **AMD Ryzen 5 5600X (6-Core)** + **32GB DDR4 RAM**.

---

## 🎬 What It Does

Flow Companion Studio bookends [Google Flow](https://flow.google.com/) so you never waste credits or time on manual busywork:

1. **Zero-Credit 3x3 Slicing**: Generates storyboard contact sheets with **Gemini 4 Argon** + **Nano Banana 2.1**, drags the 4K grid into the app, and auto-slices 9 individual 16:9 shot frames with border gutter trimming.
2. **RX 9070 XT Sequential ComfyUI Polish**: Queues frames strictly with `batch_size: 1` (`0.28` denoise + `FaceDetailer` + upscale) to stay safely within 16GB VRAM, holding a mutex so FFmpeg never competes with GPU sampling.
3. **One-Click Flow Handoff & Auto-Ingest**: Copies the motion-only prompt to clipboard, opens Explorer directly to the polished frame, tracks your Google Flow credits (50 daily / 1,000 monthly Pro), and auto-detects finished `.mp4` downloads in `~/Downloads`.
4. **Continuity Chaining**: Automatically extracts the final frame of Shot $N$ via FFmpeg (`-sseof -0.05`) to anchor Shot $N+1$ with a single click.
5. **Auto-Trim & Master Cut**: Trims dead AI start/end handles (4 frames / ~0.16s), applies a 3D `.cube` LUT (Kodak 2383 / Fuji Eterna), stitches the master MP4, and outputs an edit decision manifest for DaVinci Resolve.

---

## 🚀 Quick Start

Double-click `start.bat` or run:

```powershell
# Terminal 1: Backend
cd backend
uv run uvicorn main:app --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open your browser to: **`http://localhost:3000`**

---

## 📂 Architecture & Directory Layout

```text
flow-companion-studio/
├── start.bat                    # One-click Windows launcher
├── backend/
│   ├── main.py                  # FastAPI REST API & WebSocket event hub
│   ├── database.py              # SQLite models (projects, shots, assets)
│   ├── studio.db                # SQLite database
│   ├── services/
│   │   ├── grid_slicer.py       # 3x3 / 2x2 contact sheet slicer (Pillow)
│   │   ├── comfy_client.py      # Sequential batch_size=1 ComfyUI runner
│   │   ├── folder_watcher.py    # Downloads folder watcher (watchdog)
│   │   └── ffmpeg_pipeline.py   # Last-frame extractor, handle trimmer, LUT & concat
│   └── workflows/
│       ├── polish_api.json      # ComfyUI API workflow graph
│       └── luts/                # Master .cube 3D LUT files (Kodak 2383, Fuji Eterna)
├── frontend/                    # Next.js 16 (App Router + Tailwind CSS + Lucide)
└── projects_data/               # Media storage per project
    └── {project_slug}/
        ├── 01_grids/            # Raw 3x3 contact sheets
        ├── 02_keyframes_raw/    # Sliced 16:9 shots
        ├── 03_keyframes_polished/ # ComfyUI low-denoise skin/texture passes
        ├── 04_flow_clips/       # Downloaded Flow MP4s & extracted last frames
        └── 05_exports/          # Master cut MP4 and timeline manifest
```

---

## ⚡ Gemini 4 Argon Pre-Production Prompt

Whenever you start a scene, paste this prompt into your chat with **Gemini 4 Argon**:

```text
Act as my AI Director of Photography. For the following video concept, produce two outputs:

1. **Nano Banana 2.1 3x3 Contact Sheet Prompt**: A single detailed image generation prompt that renders a 3x3 cinematic storyboard contact sheet (9 sequential 16:9 frames in one 4K grid) with locked character anchor traits (exact facial geometry, wardrobe, lighting palette, and 35mm film stock).

2. **Flow Companion Shot List JSON**: A JSON array of 9 shot objects matching the 9 grid cells. For each shot, include:
   - "shot_number" (1 to 9)
   - "scene_title"
   - "flow_mode" ("frames" or "ingredients")
   - "flow_model" ("veo_3_1_lite" or "veo_3_1_fast")
   - "image_prompt" (for local ComfyUI 0.28-denoise skin/detail polish pass)
   - "motion_prompt" (strictly describing action path and camera movement for Google Flow)
   - "camera_move" (e.g., "slow dolly in", "tracking left", "static shallow DOF")
```
