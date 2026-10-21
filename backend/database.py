import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent / "studio.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            aspect_ratio TEXT DEFAULT '16:9',
            default_lut TEXT DEFAULT 'none',
            trim_start_frames INTEGER DEFAULT 4,
            trim_end_frames INTEGER DEFAULT 4,
            daily_credits_used INTEGER DEFAULT 0,
            monthly_credits_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL,
            name TEXT NOT NULL,
            trigger_tag TEXT,
            reference_image_path TEXT,
            anchor_traits_prompt TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            shot_number INTEGER NOT NULL,
            scene_title TEXT,
            flow_mode TEXT DEFAULT 'frames',
            flow_model TEXT DEFAULT 'veo_3_1_lite',
            image_prompt TEXT,
            motion_prompt TEXT,
            camera_move TEXT,
            raw_start_frame TEXT,
            polished_start_frame TEXT,
            raw_end_frame TEXT,
            polished_end_frame TEXT,
            flow_video_raw TEXT,
            flow_video_trimmed TEXT,
            extracted_last_frame TEXT,
            status TEXT DEFAULT 'draft',
            voiceover_line TEXT,
            duration_seconds INTEGER DEFAULT 5,
            estimated_credits INTEGER DEFAULT 10,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        # Schema migration check
        for col_def in [
            ("voiceover_line", "TEXT"),
            ("duration_seconds", "INTEGER DEFAULT 5"),
            ("estimated_credits", "INTEGER DEFAULT 10"),
        ]:
            try:
                conn.execute(f"ALTER TABLE shots ADD COLUMN {col_def[0]} {col_def[1]};")
                conn.commit()
            except Exception:
                pass

# --- Project Operations ---

def create_project(name: str, slug: str, aspect_ratio: str = "16:9", default_lut: str = "none") -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO projects (name, slug, aspect_ratio, default_lut)
            VALUES (?, ?, ?, ?)
            """,
            (name, slug, aspect_ratio, default_lut),
        )
        project_id = cursor.lastrowid
        conn.commit()
    return get_project(project_id)

def get_projects() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            p = dict(r)
            shots = conn.execute(
                "SELECT * FROM shots WHERE project_id = ? ORDER BY shot_number ASC",
                (p["id"],),
            ).fetchall()
            assets = conn.execute(
                "SELECT * FROM assets WHERE project_id = ?",
                (p["id"],),
            ).fetchall()
            p["shots"] = [dict(s) for s in shots]
            p["assets"] = [dict(a) for a in assets]
            result.append(p)
        return result

def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            return None
        project = dict(row)
        shots = conn.execute(
            "SELECT * FROM shots WHERE project_id = ? ORDER BY shot_number ASC",
            (project_id,),
        ).fetchall()
        assets = conn.execute(
            "SELECT * FROM assets WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        project["shots"] = [dict(s) for s in shots]
        project["assets"] = [dict(a) for a in assets]
        return project

def get_project_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
        if not row:
            return None
    return get_project(row["id"])

def update_project(project_id: int, **fields) -> Optional[Dict[str, Any]]:
    if not fields:
        return get_project(project_id)
    keys = list(fields.keys())
    values = list(fields.values())
    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values.append(project_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
        conn.commit()
    return get_project(project_id)

def add_credits_used(project_id: int, amount: int):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE projects
            SET daily_credits_used = daily_credits_used + ?,
                monthly_credits_used = monthly_credits_used + ?
            WHERE id = ?
            """,
            (amount, amount, project_id),
        )
        conn.commit()

# --- Shot Operations ---

def create_shot(project_id: int, shot_number: int, **fields) -> Dict[str, Any]:
    keys = ["project_id", "shot_number"] + list(fields.keys())
    values = [project_id, shot_number] + list(fields.values())
    placeholders = ", ".join(["?"] * len(keys))
    cols = ", ".join(keys)
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO shots ({cols}) VALUES ({placeholders})",
            values,
        )
        shot_id = cursor.lastrowid
        conn.commit()
    return get_shot(shot_id)

def get_shot(shot_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM shots WHERE id = ?", (shot_id,)).fetchone()
        return dict(row) if row else None

def get_shot_by_project_and_number(project_id: int, shot_number: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM shots WHERE project_id = ? AND shot_number = ?",
            (project_id, shot_number),
        ).fetchone()
        return dict(row) if row else None

def get_active_awaiting_shot(project_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        if project_id:
            row = conn.execute(
                "SELECT * FROM shots WHERE project_id = ? AND status = 'awaiting_download' ORDER BY shot_number ASC LIMIT 1",
                (project_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM shots WHERE status = 'awaiting_download' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

def update_shot(shot_id: int, **fields) -> Optional[Dict[str, Any]]:
    if not fields:
        return get_shot(shot_id)
    keys = list(fields.keys())
    values = list(fields.values())
    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values.append(shot_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE shots SET {set_clause} WHERE id = ?", values)
        conn.commit()
    return get_shot(shot_id)
