"""NuNu TV / Cocomelon-style 2D renderer with toddler characters and rich scenes."""

from __future__ import annotations

import math
import re
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config.settings import VIDEO_HEIGHT, VIDEO_WIDTH

SCENE_TYPES = ("bus", "playground", "bedroom", "meadow", "party")


def extract_script_lines(script_path) -> list[str]:
    content = Path(script_path).read_text(encoding="utf-8")
    match = re.search(r"##\s*Script\s*\n+([\s\S]+?)(?:\n##|\Z)", content, re.IGNORECASE)
    text = match.group(1).strip() if match else content
    lines = [ln.strip() for ln in text.split("\n") if ln.strip() and not ln.startswith("#")]
    return lines or [text[:120]]


def _hex(c: str) -> tuple[int, int, int]:
    return tuple(int(c.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def glossy_ellipse(draw: ImageDraw.ImageDraw, box: tuple, fill: tuple, outline: tuple | None = None) -> None:
    draw.ellipse(box, fill=fill, outline=outline, width=3)
    x0, y0, x1, y1 = box
    hw, hh = (x1 - x0) // 4, (y1 - y0) // 4
    highlight = tuple(min(255, c + 55) for c in fill)
    draw.ellipse((x0 + hw, y0 + hh, x0 + hw * 2, y0 + hh * 2), fill=highlight)


def draw_toddler(draw: ImageDraw.ImageDraw, cx: int, cy: int, frame: int, hair: str = "blonde") -> None:
    bounce = int(10 * math.sin(frame / 5))
    cy += bounce
    skin = (255, 220, 185)
    hair_color = (255, 210, 80) if hair == "blonde" else (120, 75, 45)
    shirt = (70, 150, 255)
    # body
    glossy_ellipse(draw, (cx - 75, cy + 40, cx + 75, cy + 200), shirt)
    # head
    glossy_ellipse(draw, (cx - 95, cy - 120, cx + 95, cy + 70), skin, (230, 190, 160))
    # hair tuft
    draw.ellipse((cx - 80, cy - 150, cx + 80, cy - 40), fill=hair_color)
    draw.ellipse((cx - 30, cy - 175, cx + 30, cy - 95), fill=hair_color)
    # big eyes
    for ex in (cx - 42, cx + 18):
        draw.ellipse((ex, cy - 45, ex + 38, cy - 5), fill=(255, 255, 255))
        pupil = ex + 14 + int(3 * math.sin(frame / 8))
        draw.ellipse((pupil, cy - 32, pupil + 16, cy - 14), fill=(30, 30, 50))
        draw.ellipse((pupil + 4, cy - 30, pupil + 9, cy - 23), fill=(255, 255, 255))
    # smile
    draw.arc((cx - 35, cy - 15, cx + 35, cy + 30), 15, 165, fill=(220, 90, 90), width=5)
    # waving arm
    arm_swing = int(25 * math.sin(frame / 4))
    draw.line([(cx + 70, cy + 70), (cx + 120, cy + 20 + arm_swing)], fill=skin, width=18)


def draw_bunny_friend(draw: ImageDraw.ImageDraw, cx: int, cy: int, frame: int) -> None:
    hop = int(20 * math.sin(frame / 3))
    cy -= abs(hop)
    white = (252, 252, 255)
    glossy_ellipse(draw, (cx - 55, cy - 20, cx + 55, cy + 90), white, (210, 210, 220))
    glossy_ellipse(draw, (cx - 50, cy - 110, cx + 50, cy + 10), white, (210, 210, 220))
    draw.ellipse((cx - 35, cy - 150, cx - 5, cy - 60), fill=white)
    draw.ellipse((cx + 5, cy - 150, cx + 35, cy - 60), fill=white)
    draw.ellipse((cx - 22, cy - 35, cx - 6, cy - 18), fill=(40, 40, 60))
    draw.ellipse((cx + 6, cy - 35, cx + 22, cy - 18), fill=(40, 40, 60))


def draw_yellow_bus(draw: ImageDraw.ImageDraw, base_y: int, frame: int) -> None:
    bx, by = 120, base_y - 280
    wobble = int(4 * math.sin(frame / 6))
    # body
    draw.rounded_rectangle((bx, by + wobble, bx + 520, by + 220 + wobble), radius=40, fill=(255, 210, 0), outline=(220, 160, 0), width=6)
    draw.rounded_rectangle((bx + 30, by + 40 + wobble, bx + 490, by + 150 + wobble), radius=20, fill=(180, 230, 255))
    # windows shine
    for wx in (60, 200, 340):
        draw.rounded_rectangle((bx + wx, by + 55 + wobble, bx + wx + 110, by + 135 + wobble), radius=12, fill=(210, 245, 255))
        draw.line([(bx + wx + 15, by + 60 + wobble), (bx + wx + 50, by + 95 + wobble)], fill=(255, 255, 255), width=4)
    # wheels
    for wx in (bx + 90, bx + 380):
        rot = int((frame * 12) % 360)
        draw.ellipse((wx, by + 195 + wobble, wx + 90, by + 285 + wobble), fill=(40, 40, 45))
        draw.ellipse((wx + 25, by + 220 + wobble, wx + 65, by + 260 + wobble), fill=(180, 180, 185))
        spoke_x = wx + 45 + int(15 * math.cos(math.radians(rot)))
        spoke_y = by + 240 + wobble + int(15 * math.sin(math.radians(rot)))
        draw.line([(wx + 45, by + 240 + wobble), (spoke_x, spoke_y)], fill=(120, 120, 125), width=5)


def draw_playground(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    draw.rounded_rectangle((680, base_y - 200, 780, base_y - 20), radius=15, fill=(255, 100, 100))
    draw.rounded_rectangle((820, base_y - 260, 920, base_y - 20), radius=15, fill=(100, 180, 255))
    draw.ellipse((750, base_y - 280, 850, base_y - 180), fill=(255, 220, 60), outline=(230, 180, 40), width=4)


def draw_bedroom_bg(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    draw.rectangle((0, 0, VIDEO_WIDTH, base_y), fill=(255, 230, 245))
    draw.rounded_rectangle((100, base_y - 320, 500, base_y - 40), radius=30, fill=(180, 140, 255))
    draw.rectangle((100, base_y - 120, 500, base_y - 40), fill=(255, 255, 255))
    draw.ellipse((600, base_y - 350, 750, base_y - 200), fill=(255, 245, 180))


def draw_sky_scene(draw: ImageDraw.ImageDraw, scene_idx: int, frame: int) -> int:
    palettes = [
        ("#5BC8FF", "#B8E8FF", "#6AD66A"),
        ("#89CFF0", "#FFE5B4", "#7ED957"),
        ("#FFB6C1", "#FFF0F5", "#98D98E"),
        ("#FFD93D", "#FFF8DC", "#6BCB77"),
    ]
    top, mid, hill = palettes[scene_idx % len(palettes)]
    t, m = _hex(top), _hex(mid)
    for y in range(VIDEO_HEIGHT):
        r = y / max(VIDEO_HEIGHT - 1, 1)
        color = tuple(int(t[i] + (m[i] - t[i]) * r) for i in range(3))
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=color)
    drift = int(15 * math.sin(frame / 20))
    for cx, cy, sc in [(200, 200, 1.3), (700, 160, 1.6), (950, 280, 1.0)]:
        r = int(45 * sc)
        for dx, dy, rad in [(0, 0, r), (-r, 12, int(r * 0.7)), (r, 10, int(r * 0.75))]:
            draw.ellipse((cx + dx + drift - rad, cy + dy - rad, cx + dx + drift + rad, cy + dy + rad), fill=(255, 255, 255))
    base_y = 1350
    draw.polygon([(0, base_y), (VIDEO_WIDTH, base_y - 30), (VIDEO_WIDTH, VIDEO_HEIGHT), (0, VIDEO_HEIGHT)], fill=_hex(hill))
    return base_y


def draw_stars(draw: ImageDraw.ImageDraw, frame: int) -> None:
    rng = random.Random(99)
    for i in range(25):
        x, y = rng.randint(30, VIDEO_WIDTH - 30), rng.randint(40, 500)
        s = 4 + (i + frame) % 4
        if (i + frame) % 7 < 4:
            draw.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=(255, 255, 200))


def render_cartoon_frame(line: str, line_idx: int, total_lines: int, frame_idx: int, frames_in_scene: int) -> Image.Image:
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    scene = SCENE_TYPES[line_idx % len(SCENE_TYPES)]
    base_y = draw_sky_scene(draw, line_idx, frame_idx)
    draw_stars(draw, frame_idx)

    if scene == "bus":
        draw_yellow_bus(draw, base_y, frame_idx)
        draw_toddler(draw, 720, base_y - 60, frame_idx, "blonde")
        draw_bunny_friend(draw, 900, base_y - 30, frame_idx)
    elif scene == "playground":
        draw_playground(draw, base_y)
        draw_toddler(draw, 480, base_y - 50, frame_idx, "brown")
        draw_bunny_friend(draw, 650, base_y - 20, frame_idx)
    elif scene == "bedroom":
        draw_bedroom_bg(draw, base_y)
        draw_toddler(draw, 540, base_y - 80, frame_idx, "blonde")
        draw_bunny_friend(draw, 750, base_y - 40, frame_idx)
    else:
        draw.ellipse((750, 180, 950, 380), fill=(255, 230, 100))
        draw_toddler(draw, 500, base_y - 50, frame_idx, "blonde")
        draw_bunny_friend(draw, 300, base_y - 30, frame_idx)

    # subtitle pill (NuNu style)
    font = load_font(44)
    words = line.split()
    caption = " ".join(words[:9]) + ("..." if len(words) > 9 else "")
    pad = 28
    bbox = draw.textbbox((0, 0), caption, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px = (VIDEO_WIDTH - tw) // 2 - pad
    py = VIDEO_HEIGHT - 200
    draw.rounded_rectangle((px, py, px + tw + pad * 2, py + th + pad * 2), radius=30, fill=(255, 90, 120))
    draw.text((px + pad + 2, py + pad + 2), caption, font=font, fill=(120, 20, 40))
    draw.text((px + pad, py + pad), caption, font=font, fill=(255, 255, 255))

    return img
