import asyncio
import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from services.comfy_client import ComfySequentialRunner
from services.ffmpeg_pipeline import assemble_master_cut, extract_last_frame
from services.folder_watcher import FlowDownloadsWatcher
from services.grid_slicer import slice_contact_sheet

# --- Paths & Initial Setup ---
BASE_DIR = Path(__file__).parent
PROJECTS_DATA_DIR = BASE_DIR.parent / "projects_data"
PROJECTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
LUTS_DIR = BASE_DIR / "workflows" / "luts"
LUTS_DIR.mkdir(parents=True, exist_ok=True)

# Services
comfy_runner = ComfySequentialRunner()
folder_watcher = FlowDownloadsWatcher()

# Active WebSockets
connected_websockets: List[WebSocket] = []

async def broadcast_event(event_type: str, data: Any = None):
    payload = {"type": event_type, "data": data}
    dead_sockets = []
    for ws in connected_websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead_sockets.append(ws)
    for ws in dead_sockets:
        if ws in connected_websockets:
            connected_websockets.remove(ws)

def on_downloaded_video(video_path: str):
    """Callback from watchdog running on background thread when Flow downloads an MP4."""
    print(f"[Watcher] Ingesting downloaded video: {video_path}")
    active_shot = db.get_active_awaiting_shot()
    if not active_shot:
        print("[Watcher] No shot currently awaiting download.")
        return

    shot_id = active_shot["id"]
    project_id = active_shot["project_id"]
    project = db.get_project(project_id)
    if not project:
        return

    slug = project["slug"]
    shot_num = active_shot["shot_number"]
    dest_dir = PROJECTS_DATA_DIR / slug / "04_flow_clips"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"shot_{shot_num:02d}_raw.mp4"

    # Move or copy downloaded file
    try:
        shutil.copy2(video_path, dest_path)
    except Exception as e:
        print(f"[Watcher] File copy error: {e}")
        return

    # Extract last frame for continuity
    last_frame_path = dest_dir / f"shot_{shot_num:02d}_last_frame.png"
    try:
        extract_last_frame(str(dest_path), str(last_frame_path))
        extracted_rel = last_frame_path.relative_to(PROJECTS_DATA_DIR / slug).as_posix()
    except Exception as e:
        print(f"[Watcher] Extract last frame error: {e}")
        extracted_rel = None

    rel_video_path = dest_path.relative_to(PROJECTS_DATA_DIR / slug).as_posix()
    db.update_shot(
        shot_id,
        flow_video_raw=rel_video_path,
        extracted_last_frame=extracted_rel,
        status="completed",
    )
    print(f"[Watcher] Successfully ingested Shot #{shot_num} to {dest_path}")

    # Notify frontend via event loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(
            broadcast_event("clip_ingested", {"shot_id": shot_id, "project_id": project_id}),
            loop,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.init_db()
    folder_watcher.start(on_downloaded_video)
    yield
    # Shutdown
    folder_watcher.stop()


app = FastAPI(title="Flow Companion Studio API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static media mount
app.mount("/media", StaticFiles(directory=str(PROJECTS_DATA_DIR)), name="media")


# --- WebSocket Hub ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


# --- Models ---
class ProjectCreate(BaseModel):
    name: str
    slug: str
    aspect_ratio: str = "16:9"
    default_lut: str = "none"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    default_lut: Optional[str] = None
    trim_start_frames: Optional[int] = None
    trim_end_frames: Optional[int] = None

class ShotImportItem(BaseModel):
    shot_number: int
    scene_title: Optional[str] = None
    flow_mode: Optional[str] = "frames"
    flow_model: Optional[str] = "veo_3_1_lite"
    image_prompt: Optional[str] = None
    motion_prompt: Optional[str] = None
    camera_move: Optional[str] = None
    voiceover_line: Optional[str] = None
    duration_seconds: Optional[int] = 5
    estimated_credits: Optional[int] = 10
    raw_start_frame: Optional[str] = None
    raw_end_frame: Optional[str] = None

class ShotPolishRequest(BaseModel):
    denoise: float = 0.28
    prompt_override: Optional[str] = None
    seed: Optional[int] = None


# --- Project Routes ---

@app.get("/api/projects")
def list_projects():
    return db.get_projects()

@app.post("/api/projects")
def create_project(payload: ProjectCreate):
    # Ensure project slug folder structure
    slug_dir = PROJECTS_DATA_DIR / payload.slug
    for sub in ["01_grids", "02_keyframes_raw", "03_keyframes_polished", "04_flow_clips", "05_exports"]:
        (slug_dir / sub).mkdir(parents=True, exist_ok=True)

    project = db.create_project(
        name=payload.name,
        slug=payload.slug,
        aspect_ratio=payload.aspect_ratio,
        default_lut=payload.default_lut,
    )
    return project

@app.get("/api/projects/{project_id}")
def get_project(project_id: int):
    proj = db.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@app.put("/api/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    proj = db.update_project(project_id, **update_data)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@app.post("/api/projects/{project_id}/import-shots")
async def import_shots(project_id: int, shots: List[ShotImportItem]):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    created = []
    for s in shots:
        existing = db.get_shot_by_project_and_number(project_id, s.shot_number)
        shot_fields = {
            "scene_title": s.scene_title,
            "flow_mode": s.flow_mode or "frames",
            "flow_model": s.flow_model or "veo_3_1_lite",
            "image_prompt": s.image_prompt,
            "motion_prompt": s.motion_prompt,
            "camera_move": s.camera_move,
            "voiceover_line": s.voiceover_line,
            "duration_seconds": s.duration_seconds or 5,
            "estimated_credits": s.estimated_credits or 10,
        }
        if s.raw_start_frame:
            shot_fields["raw_start_frame"] = s.raw_start_frame
        if s.raw_end_frame:
            shot_fields["raw_end_frame"] = s.raw_end_frame

        if existing:
            updated = db.update_shot(existing["id"], **shot_fields)
            created.append(updated)
        else:
            shot_fields["status"] = "draft"
            new_shot = db.create_shot(
                project_id=project_id,
                shot_number=s.shot_number,
                **shot_fields,
            )
            created.append(new_shot)

    await broadcast_event("shots_updated", {"project_id": project_id})
    return db.get_project(project_id)


# --- 3x3 Slicer Routes ---

@app.post("/api/projects/{project_id}/slice-grid")
async def slice_grid_endpoint(
    project_id: int,
    file: UploadFile = File(...),
    rows: int = Form(3),
    cols: int = Form(3),
    gutter_pct: float = Form(0.012),
):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    slug = project["slug"]
    grid_dir = PROJECTS_DATA_DIR / slug / "01_grids"
    raw_dir = PROJECTS_DATA_DIR / slug / "02_keyframes_raw"
    grid_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    grid_file_path = grid_dir / f"grid_input_{int(asyncio.get_event_loop().time())}.png"
    with open(grid_file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Slice contact sheet
    saved_paths = slice_contact_sheet(
        grid_image_path=str(grid_file_path),
        output_dir=str(raw_dir),
        rows=rows,
        cols=cols,
        gutter_pct=gutter_pct,
    )

    # Populate Shot Cards
    for idx, path_str in enumerate(saved_paths, start=1):
        rel_path = Path(path_str).relative_to(PROJECTS_DATA_DIR / slug).as_posix()
        existing = db.get_shot_by_project_and_number(project_id, idx)
        if existing:
            db.update_shot(existing["id"], raw_start_frame=rel_path, status="sliced")
        else:
            db.create_shot(
                project_id=project_id,
                shot_number=idx,
                scene_title=f"Shot {idx}",
                raw_start_frame=rel_path,
                status="sliced",
            )

    await broadcast_event("grid_sliced", {"project_id": project_id, "slices_count": len(saved_paths)})
    return db.get_project(project_id)


# --- ComfyUI Polish Routes ---

@app.get("/api/comfy/status")
async def comfy_status():
    available = await comfy_runner.is_available()
    return {
        "is_busy": comfy_runner.is_busy,
        "current_task": comfy_runner.current_task_info,
        "available": available,
    }

@app.post("/api/shots/{shot_id}/polish")
async def polish_shot(shot_id: int, payload: ShotPolishRequest = ShotPolishRequest()):
    shot = db.get_shot(shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    project = db.get_project(shot["project_id"])
    slug = project["slug"]
    raw_frame_rel = shot["raw_start_frame"]
    if not raw_frame_rel:
        raise HTTPException(status_code=400, detail="Shot has no raw start frame to polish")

    input_full_path = PROJECTS_DATA_DIR / slug / raw_frame_rel
    polished_dir = PROJECTS_DATA_DIR / slug / "03_keyframes_polished"
    polished_dir.mkdir(parents=True, exist_ok=True)
    output_full_path = polished_dir / f"shot_{shot['shot_number']:02d}_polished.png"

    db.update_shot(shot_id, status="polishing")
    await broadcast_event("shot_polishing", {"shot_id": shot_id})

    try:
        prompt = payload.prompt_override or shot.get("image_prompt") or ""
        result = await comfy_runner.polish_keyframe(
            input_image_path=str(input_full_path),
            output_image_path=str(output_full_path),
            prompt_text=prompt,
            denoise=payload.denoise,
            seed=payload.seed,
            use_fallback_if_offline=True,
        )
        rel_polished = output_full_path.relative_to(PROJECTS_DATA_DIR / slug).as_posix()
        updated = db.update_shot(shot_id, polished_start_frame=rel_polished, status="ready_for_flow")
        await broadcast_event("shot_updated", {"shot_id": shot_id})
        return {"result": result, "shot": updated}
    except Exception as e:
        db.update_shot(shot_id, status="sliced")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/polish-all")
async def polish_all_shots(project_id: int):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    async def _run_batch():
        for shot in project["shots"]:
            if shot.get("raw_start_frame"):
                try:
                    await polish_shot(shot["id"])
                except Exception as e:
                    print(f"[Batch Polish] Error on shot {shot['id']}: {e}")

    asyncio.create_task(_run_batch())
    return {"message": "Started batch polish queue for RX 9070 XT (batch_size: 1)"}


# --- Flow Handoff & Credits ---

MODEL_CREDIT_MAP = {
    "veo_3_1_lite": 10,
    "veo_3_1_fast": 20,
    "veo_3_1_quality": 100,
    "omni_flash_720p": 12,
    "omni_flash_360p": 6,
}

@app.post("/api/shots/{shot_id}/mark-awaiting-flow")
def mark_awaiting_flow(shot_id: int):
    shot = db.get_shot(shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    project = db.get_project(shot["project_id"])
    slug = project["slug"]

    # Calculate credit cost
    model_name = shot.get("flow_model") or "veo_3_1_lite"
    credit_cost = MODEL_CREDIT_MAP.get(model_name, 10)
    db.add_credits_used(project["id"], credit_cost)

    updated_shot = db.update_shot(shot_id, status="awaiting_download")

    # Reveal in explorer
    frame_rel = shot.get("polished_start_frame") or shot.get("raw_start_frame")
    if frame_rel:
        target_file = PROJECTS_DATA_DIR / slug / frame_rel
        if target_file.exists():
            try:
                # Open Windows Explorer and highlight the file
                subprocess.Popen(f'explorer /select,"{str(target_file)}"', shell=True)
            except Exception as e:
                print(f"[Explorer] Open error: {e}")

    return {
        "shot": updated_shot,
        "credits_deducted": credit_cost,
        "motion_prompt": shot.get("motion_prompt") or "",
        "project": db.get_project(project["id"]),
    }

@app.post("/api/shots/{shot_id}/use-prev-last-frame")
async def use_prev_last_frame(shot_id: int):
    shot = db.get_shot(shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    prev_shot = db.get_shot_by_project_and_number(shot["project_id"], shot["shot_number"] - 1)
    if not prev_shot or not prev_shot.get("extracted_last_frame"):
        raise HTTPException(status_code=400, detail="Previous shot does not have an extracted last frame")

    updated = db.update_shot(
        shot_id,
        raw_start_frame=prev_shot["extracted_last_frame"],
        status="sliced",
    )
    await broadcast_event("shot_updated", {"shot_id": shot_id})
    return updated

@app.post("/api/shots/{shot_id}/attach-clip")
async def attach_clip(shot_id: int, file: UploadFile = File(...)):
    """Manual upload or drag-and-drop of Flow video clip."""
    shot = db.get_shot(shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    project = db.get_project(shot["project_id"])
    slug = project["slug"]
    dest_dir = PROJECTS_DATA_DIR / slug / "04_flow_clips"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"shot_{shot['shot_number']:02d}_raw.mp4"

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    # Extract last frame
    last_frame_path = dest_dir / f"shot_{shot['shot_number']:02d}_last_frame.png"
    try:
        extract_last_frame(str(dest_path), str(last_frame_path))
        extracted_rel = last_frame_path.relative_to(PROJECTS_DATA_DIR / slug).as_posix()
    except Exception as e:
        print(f"[Manual Clip] Extract last frame error: {e}")
        extracted_rel = None

    rel_video_path = dest_path.relative_to(PROJECTS_DATA_DIR / slug).as_posix()
    updated = db.update_shot(
        shot_id,
        flow_video_raw=rel_video_path,
        extracted_last_frame=extracted_rel,
        status="completed",
    )
    await broadcast_event("clip_ingested", {"shot_id": shot_id, "project_id": project["id"]})
    return updated


# --- LUTs & Master Cut Assembly ---

@app.get("/api/luts")
def list_luts():
    luts = ["none"]
    for p in LUTS_DIR.glob("*.cube"):
        luts.append(p.stem)
    return luts

@app.post("/api/projects/{project_id}/assemble")
async def assemble_project(project_id: int):
    if comfy_runner.is_busy:
        raise HTTPException(status_code=409, detail="ComfyUI is currently sampling. Waiting to avoid CPU/GPU contention.")

    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    slug = project["slug"]
    completed_shots = [s for s in project["shots"] if s.get("flow_video_raw")]
    if not completed_shots:
        raise HTTPException(status_code=400, detail="No completed video shots available to assemble")

    video_paths = [str(PROJECTS_DATA_DIR / slug / s["flow_video_raw"]) for s in completed_shots]
    out_master_path = PROJECTS_DATA_DIR / slug / "05_exports" / "master_cut.mp4"

    # LUT check
    lut_choice = project.get("default_lut", "none")
    lut_file = None
    if lut_choice and lut_choice != "none":
        potential_lut = LUTS_DIR / f"{lut_choice}.cube"
        if potential_lut.exists():
            lut_file = str(potential_lut)

    try:
        assemble_master_cut(
            shot_video_paths=video_paths,
            output_master_path=str(out_master_path),
            trim_start_frames=project.get("trim_start_frames", 4),
            trim_end_frames=project.get("trim_end_frames", 4),
            lut_path=lut_file,
            fps=24,
        )
        return {
            "status": "success",
            "master_url": f"/media/{slug}/05_exports/master_cut.mp4",
            "total_shots": len(video_paths),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
