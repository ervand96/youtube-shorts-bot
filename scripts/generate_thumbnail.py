"""Generate bright click-worthy YouTube thumbnails for kids Shorts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
THUMBS = ROOT / "assets" / "thumbnails"

THUMB_W, THUMB_H = 1280, 720

CATEGORY_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "nursery": ((255, 200, 50), (255, 120, 40)),
    "bedtime": ((120, 100, 220), (60, 50, 140)),
    "learning": ((60, 160, 255), (20, 100, 200)),
    "moral": ((255, 100, 150), (200, 50, 100)),
    "animals": ((100, 200, 80), (40, 140, 50)),
}

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def hook_from_metadata(meta: dict) -> str:
    desc = meta.get("description", "")
    first = desc.split("\n")[0].strip() if desc else ""
    if first:
        return first.rstrip("!")
    title = meta.get("title", "Benny's Story World")
    return title.split("|")[0].strip().upper()


def wrap_title(text: str, max_chars: int = 18) -> list[str]:
    words = text.upper().split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if len(trial) > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines[:3]


def draw_benny_mini(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    skin = (255, 218, 185)
    draw.ellipse((cx - 70, cy - 80, cx + 70, cy + 60), fill=skin, outline=(220, 180, 150), width=4)
    draw.ellipse((cx - 60, cy - 110, cx + 60, cy - 30), fill=(255, 200, 60))
    draw.rounded_rectangle((cx - 55, cy + 40, cx + 55, cy + 160), radius=25, fill=(50, 130, 230))
    for ex in (cx - 35, cx + 5):
        draw.ellipse((ex, cy - 45, ex + 28, cy - 15), fill=(255, 255, 255))
        draw.ellipse((ex + 8, cy - 38, ex + 20, cy - 26), fill=(40, 40, 60))


def generate_thumbnail(metadata_path: Path, output_path: Path) -> Path:
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    category = meta.get("category", "nursery")
    c1, c2 = CATEGORY_COLORS.get(category, CATEGORY_COLORS["nursery"])
    hook = hook_from_metadata(meta)

    img = Image.new("RGB", (THUMB_W, THUMB_H), c1)
    draw = ImageDraw.Draw(img)
    for y in range(THUMB_H):
        t = y / THUMB_H
        color = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        draw.line([(0, y), (THUMB_W, y)], fill=color)

    # decorative circles
    for cx, cy, r, alpha in [(200, 150, 120, 40), (1050, 500, 180, 30), (900, 120, 90, 50)]:
        layer = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, alpha))
        img.paste(layer, (0, 0), layer)
        draw = ImageDraw.Draw(img)

    draw_benny_mini(draw, 980, 380)

    lines = wrap_title(hook)
    font_big = load_font(92 if len(lines) <= 2 else 72)
    font_sub = load_font(36)

    block_h = len(lines) * 100 + 20
    y = (THUMB_H - block_h) // 2 - 20
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_big)
        tw = bbox[2] - bbox[0]
        x = 80
        for ox, oy in [(-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3)]:
            draw.text((x + ox, y + oy), line, font=font_big, fill=(20, 20, 40))
        draw.text((x, y), line, font=font_big, fill=(255, 255, 255))
        y += 100

    draw.text((80, THUMB_H - 70), "Benny's Story World", font=font_sub, fill=(255, 255, 220))
    draw.rounded_rectangle((60, 40, 420, 110), radius=24, fill=(255, 255, 255))
    draw.text((85, 58), "KIDS CARTOON", font=load_font(32), fill=c2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    return output_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate YouTube thumbnail PNG")
    parser.add_argument("--id", required=True, help="e.g. 2026-07-08-1")
    parser.add_argument("--metadata", help="Metadata JSON override")
    args = parser.parse_args()

    meta_path = Path(args.metadata) if args.metadata else ROOT / "videos" / f"{args.id}-metadata.json"
    out = THUMBS / f"{args.id}.png"
    path = generate_thumbnail(meta_path, out)
    print(path)


if __name__ == "__main__":
    main()
