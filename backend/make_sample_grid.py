"""Generates a 3x3 contact sheet image for the Christian YouTube documentary on 1 Enoch."""
from PIL import Image, ImageDraw
from pathlib import Path

def generate_sample_contact_sheet():
    width = 3840
    height = 2160
    rows = 3
    cols = 3
    cell_w = width // cols
    cell_h = height // rows

    img = Image.new("RGB", (width, height), color=(12, 10, 16))
    draw = ImageDraw.Draw(img)

    colors = [
        (45, 30, 20),  # 1. Ancient Parchment
        (25, 35, 45),  # 2. Mount Hermon Twilight
        (35, 25, 50),  # 3. Descent of Watchers
        (65, 45, 15),  # 4. Throne of Fire
        (20, 50, 40),  # 5. Ophanim Wheel of Eyes
        (55, 25, 20),  # 6. Burning Seraphim
        (20, 30, 55),  # 7. Storehouses of Stars
        (50, 40, 25),  # 8. Archangel Michael
        (30, 25, 35),  # 9. Title Card
    ]

    shot_titles = [
        "Shot 01: Ancient Hebrew Scroll Macro",
        "Shot 02: Mount Hermon Twilight Summit",
        "Shot 03: Descent of the Watchers",
        "Shot 04: Throne of the Ancient of Days",
        "Shot 05: Ophanim - Living Wheels of Eyes",
        "Shot 06: Six-Winged Burning Seraphim",
        "Shot 07: Cosmic Storehouses of Stars",
        "Shot 08: Archangel Michael & Scales",
        "Shot 09: Title - THE BOOK OF ENOCH",
    ]

    idx = 0
    for r in range(rows):
        for c in range(cols):
            x1 = c * cell_w
            y1 = r * cell_h
            x2 = (c + 1) * cell_w
            y2 = (r + 1) * cell_h

            bg_color = colors[idx % len(colors)]
            draw.rectangle([x1 + 6, y1 + 6, x2 - 6, y2 - 6], fill=bg_color, outline=(215, 175, 75), width=4)

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            draw.line([cx - 40, cy, cx + 40, cy], fill=(255, 255, 255, 120), width=2)
            draw.line([cx, cy - 40, cx, cy + 40], fill=(255, 255, 255, 120), width=2)

            label = f"[{idx + 1}] {shot_titles[idx]}"
            draw.text((x1 + 40, y1 + 40), label, fill=(255, 235, 170))
            draw.text((x1 + 40, y2 - 60), "16:9 • 4K • Chiaroscuro Sacred Art • 1 Enoch Lore", fill=(200, 195, 190))
            idx += 1

    dest = Path(__file__).parent / "sample_enoch_contact_sheet_3x3.png"
    img.save(dest, format="PNG")
    print(f"Generated sample 1 Enoch contact sheet: {dest}")
    return dest

if __name__ == "__main__":
    generate_sample_contact_sheet()
