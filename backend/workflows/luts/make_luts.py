"""Generates warm cinematic 3D LUTs (.cube) for Flow Companion Studio."""
import math
from pathlib import Path

def create_cube_lut(filename: str, title: str, size: int = 17, warmth: float = 0.04, contrast: float = 1.15):
    lines = [
        f'TITLE "{title}"',
        f"LUT_3D_SIZE {size}",
        "# Flow Companion Studio cinematic tone mapper",
        ""
    ]
    for b in range(size):
        bv = b / (size - 1)
        for g in range(size):
            gv = g / (size - 1)
            for r in range(size):
                rv = r / (size - 1)

                # Apply subtle S-curve contrast
                def s_curve(x, p=contrast):
                    return (math.sin((x - 0.5) * math.pi) * 0.5 + 0.5) * (p - 1.0) + x

                r_out = min(1.0, max(0.0, s_curve(rv) * (1.0 + warmth)))
                g_out = min(1.0, max(0.0, s_curve(gv)))
                b_out = min(1.0, max(0.0, s_curve(bv) * (1.0 - warmth * 0.5)))

                lines.append(f"{r_out:.6f} {g_out:.6f} {b_out:.6f}")

    out_path = Path(__file__).parent / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Generated LUT: {out_path}")

if __name__ == "__main__":
    create_cube_lut("kodak_2383.cube", "Kodak 2383 Print Warmth", size=17, warmth=0.05, contrast=1.12)
    create_cube_lut("fuji_eterna.cube", "Fuji Eterna Soft Cine", size=17, warmth=-0.02, contrast=1.06)
