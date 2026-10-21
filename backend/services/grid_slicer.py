from pathlib import Path
from typing import List, Tuple
from PIL import Image

def slice_contact_sheet(
    grid_image_path: str,
    output_dir: str,
    rows: int = 3,
    cols: int = 3,
    gutter_pct: float = 0.012,
) -> List[str]:
    """
    Slices a contact sheet (e.g., 3x3 Nano Banana 2.1 grid) into individual shot frames,
    shaving a configurable gutter percentage off each cell edge to prevent borders from bleeding into Flow.
    """
    img = Image.open(grid_image_path).convert("RGB")
    width, height = img.size
    cell_w = width / cols
    cell_h = height / rows

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    idx = 1
    for r in range(rows):
        for c in range(cols):
            pad_x = cell_w * gutter_pct
            pad_y = cell_h * gutter_pct
            left = int(c * cell_w + pad_x)
            top = int(r * cell_h + pad_y)
            right = int((c + 1) * cell_w - pad_x)
            bottom = int((r + 1) * cell_h - pad_y)

            cell = img.crop((left, top, right, bottom))
            out_path = out_dir / f"shot_{idx:02d}_raw.png"
            cell.save(out_path, format="PNG")
            saved_paths.append(str(out_path))
            idx += 1

    return saved_paths

def get_grid_dimensions(grid_image_path: str) -> Tuple[int, int]:
    with Image.open(grid_image_path) as img:
        return img.size
