"""Seeds the Christian YouTube Channel documentary production project."""
import sys
from pathlib import Path

# Add backend directory to path
sys.path.append(str(Path(__file__).parent))

import database as db

def seed():
    db.init_db()

    # Clear previous demo data
    with db.get_connection() as conn:
        conn.execute("DELETE FROM projects WHERE slug = 'deus_vult_michael'")
        conn.commit()

    existing = db.get_project_by_slug("watchers_of_enoch")
    if existing:
        print(f"Project already exists: {existing['name']}")
        return

    proj = db.create_project(
        name="The Watchers & The Cosmic Council (1 Enoch Episode)",
        slug="watchers_of_enoch",
        aspect_ratio="16:9",
        default_lut="kodak_2383",
    )
    print(f"Created project: {proj['name']} (ID: {proj['id']})")

    # 9 Documentary B-Roll & Visual Narrative Shots
    shots_data = [
        {
            "shot_number": 1,
            "scene_title": "Ancient Ge'ez & Hebrew Scroll Unfurling",
            "camera_move": "macro slow slider",
            "image_prompt": "cinematic 35mm macro shot of ancient cracked parchment manuscript with Hebrew and Ge'ez sacred lettering, warm dramatic candlelight, floating dust motes, chiaroscuro lighting",
            "motion_prompt": "Slow smooth macro slider moving left to right across the aged parchment as flickering candlelight dances across the ink",
        },
        {
            "shot_number": 2,
            "scene_title": "Mount Hermon at Ominous Twilight",
            "camera_move": "slow aerial push-in",
            "image_prompt": "epic aerial view of Mount Hermon summit shrouded in swirling dark storm clouds at twilight, jagged ancient limestone peaks, atmospheric fog, photorealistic sacred realism",
            "motion_prompt": "Slow aerial dolly pushing through heavy mist toward the jagged mountain summit as lightning flashes deep within the cloud bank",
        },
        {
            "shot_number": 3,
            "scene_title": "Descent of the Luminous Watchers",
            "camera_move": "low angle tilt up",
            "image_prompt": "low angle view from barren earth looking up into night sky, twenty towering ethereal celestial beings descending from heaven in streaks of golden starlight, mysterious majestic silhouettes",
            "motion_prompt": "Low angle camera slowly tilting upward as radiant pillars of starlight descend from the cosmos onto the mountain ridges",
        },
        {
            "shot_number": 4,
            "scene_title": "The Throne of the Ancient of Days",
            "camera_move": "grand slow dolly back",
            "image_prompt": "majestic vision of the Throne of God from Daniel 7, river of fire pouring out from the crystal pavement, divine brilliant white radiance, awe-inspiring reverence, sacred biblical art",
            "motion_prompt": "Grand slow dolly backwards revealing the immense cosmic throne and river of molten light flowing across crystalline floor",
        },
        {
            "shot_number": 5,
            "scene_title": "The Ophanim: Living Wheels Full of Eyes",
            "camera_move": "orbital swirl",
            "image_prompt": "biblically accurate Ophanim angel from Ezekiel 1, beryl colored concentric wheels within wheels covered in living eyes, burning with emerald and golden spiritual fire",
            "motion_prompt": "Mesmerizing orbital camera movement rotating around the gyroscopic concentric wheels as holy flames lick the rim and eyes blink in solemn reverence",
        },
        {
            "shot_number": 6,
            "scene_title": "The Burning Seraphim with Six Wings",
            "camera_move": "slow tracking shot",
            "image_prompt": "biblically accurate Seraph angel from Isaiah 6, six fiery feathered wings (two covering face, two covering feet, two flying), holding a glowing coal with tongs, solemn awe",
            "motion_prompt": "Slow steady tracking push toward the towering burning seraph as embers drift and the massive wings undulate with gentle holy grace",
        },
        {
            "shot_number": 7,
            "scene_title": "Enoch Guided Through the Storehouses of the Stars",
            "camera_move": "forward crane shot",
            "image_prompt": "ancient prophet in simple linen robes walking alongside radiant guiding angel Uriel through cosmic corridors of stars, celestial chambers and planetary orbits",
            "motion_prompt": "Smooth forward crane shot following the prophet and angel as nebulae and revolving celestial spheres drift past in deep space",
        },
        {
            "shot_number": 8,
            "scene_title": "Archangel Michael and the Divine Verdict",
            "camera_move": "dramatic push-in",
            "image_prompt": "close-up of Archangel Michael standing before the heavenly council, holding golden scales of divine justice, solemn determined expression, ornate golden armor, deep chiaroscuro",
            "motion_prompt": "Slow dramatic push-in on Michael's face as divine golden light reflects in his eyes and the heavenly council gathers in the background",
        },
        {
            "shot_number": 9,
            "scene_title": "Title Card: THE BOOK OF ENOCH",
            "camera_move": "static lock-off",
            "image_prompt": "ancient stone inscription illuminated by warm torchlight, carved with 'THE BOOK OF ENOCH', deep cinematic anamorphic bokeh, dust motes in beam of light",
            "motion_prompt": "Static shot with atmospheric dust particles floating in a diagonal light beam as the carved title emerges from deep shadow",
        },
    ]

    for s in shots_data:
        db.create_shot(
            project_id=proj["id"],
            shot_number=s["shot_number"],
            scene_title=s["scene_title"],
            camera_move=s["camera_move"],
            image_prompt=s["image_prompt"],
            motion_prompt=s["motion_prompt"],
            flow_model="veo_3_1_lite",
            status="draft",
        )

    print("Successfully seeded 9 shots for The Watchers & The Cosmic Council!")

if __name__ == "__main__":
    seed()
