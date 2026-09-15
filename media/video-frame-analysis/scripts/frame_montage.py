#!/usr/bin/env python3
"""Build a labelled frame montage from a video for vision-model inspection.

Usage:
  python frame_montage.py VIDEO OUT.jpg --crop-name near \
      --row '0.6,3.0,3.4' --row '10.4,12.5,13.0'

Each --row is a comma-separated timestamp list (seconds); one grid row per --row.
A timestamp may carry a crop suffix (`3.0:far`) to override --crop-name for that
cell. Crops are normalized boxes (x1,y1,x2,y2 as fractions of the frame):
  --crop near=0,0.30,0.55,1.0
Defaults suit a fixed side-on shot with the subject left / opponent upper-right —
always verify the first montage actually contains the subject before building more
from the same coordinates.
"""
import argparse
import subprocess
import sys

from PIL import Image, ImageDraw

DEFAULT_CROPS = {
    "near": (0.00, 0.30, 0.55, 1.00),   # subject left / lower half
    "far": (0.40, 0.05, 1.00, 0.85),    # opponent right / upper half
    "full": (0.00, 0.00, 1.00, 1.00),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--row", action="append", required=True,
                    help="comma-separated timestamps in seconds (one grid row)")
    ap.add_argument("--crop", action="append", default=[],
                    help="name=x1,y1,x2,y2 fractions (repeatable)")
    ap.add_argument("--crop-name", default="full",
                    help="crop used when a timestamp has no :side suffix")
    ap.add_argument("--cell", default="520x340")
    ap.add_argument("--quality", type=int, default=92)
    a = ap.parse_args()

    crops = dict(DEFAULT_CROPS)
    for spec in a.crop:
        name, _, box = spec.partition("=")
        crops[name] = tuple(float(v) for v in box.split(","))
    cw, ch = (int(v) for v in a.cell.lower().split("x"))
    rows = [[t for t in r.split(",") if t.strip()] for r in a.row]

    def frame(ts: str, side: str) -> Image.Image:
        p = f"/tmp/_montage_{side}_{ts.replace(':', '_')}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", ts, "-i", a.video,
                        "-frames:v", "1", p], check=True)
        return Image.open(p)

    n = max(len(r) for r in rows)
    canvas = Image.new("RGB", (cw * n, ch * len(rows)), "black")
    draw = ImageDraw.Draw(canvas)
    for ri, row in enumerate(rows):
        for ci, spec in enumerate(row):
            ts, _, side = spec.partition(":")
            side = side or a.crop_name
            img = frame(ts, side)
            w, h = img.size
            x1, y1, x2, y2 = crops.get(side, crops["full"])
            cell = img.crop((int(w * x1), int(h * y1), int(w * x2), int(h * y2))).resize((cw, ch), Image.LANCZOS)
            canvas.paste(cell, (ci * cw, ri * ch))
            draw.rectangle([ci * cw, ri * ch, ci * cw + 190, ri * ch + 24], fill="black")
            draw.text((ci * cw + 6, ri * ch + 8), f"t={ts}s {side}", fill="yellow")
    canvas.save(a.out, quality=a.quality)
    print(a.out, canvas.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
