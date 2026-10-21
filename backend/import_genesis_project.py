"""Imports the Genesis Creation Week 9:16 vertical shots into the studio database."""
import json
import sys
from pathlib import Path

# Add backend directory to path
sys.path.append(str(Path(__file__).parent))

import database as db

def import_genesis():
    db.init_db()

    json_path = Path("c:/Users/Reforged/Downloads/genesis_vertical_9x16_shots.json")
    with open(json_path, "r", encoding="utf-8") as f:
        shots_data = json.load(f)

    # Check or create project
    slug = "genesis_creation_vertical"
    existing = db.get_project_by_slug(slug)
    if existing:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM projects WHERE slug = ?", (slug,))
            conn.commit()

    proj = db.create_project(
        name="Genesis: The Creation Week (9:16 Vertical)",
        slug=slug,
        aspect_ratio="9:16",
        default_lut="primeval_imax_65mm",
    )
    print(f"Created Project: {proj['name']} (ID: {proj['id']})")

    for s in shots_data:
        shot_num = s["shot_number"]
        raw_start = f"02_keyframes_raw/shot_{shot_num:02d}_start_9x16.png"
        raw_end = f"02_keyframes_raw/shot_{shot_num:02d}_end_9x16.png"

        db.create_shot(
            project_id=proj["id"],
            shot_number=shot_num,
            scene_title=s.get("scene_title"),
            flow_mode=s.get("flow_mode", "frames_first_and_last"),
            flow_model=s.get("flow_model", "veo_3_1_fast"),
            image_prompt=s.get("image_prompt"),
            motion_prompt=s.get("motion_prompt"),
            camera_move=s.get("camera_move"),
            voiceover_line=s.get("voiceover_line"),
            duration_seconds=s.get("duration_seconds", 6),
            estimated_credits=s.get("estimated_credits", 15),
            raw_start_frame=raw_start,
            raw_end_frame=raw_end,
            status="sliced",
        )

    print(f"Successfully imported all {len(shots_data)} shots with Start/End frames and voiceover scripts!")

if __name__ == "__main__":
    import_genesis()
