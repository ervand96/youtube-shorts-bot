"""Draw kids cartoon scene frames with characters and animation."""

from __future__ import annotations

import math
import re
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config.settings import VIDEO_HEIGHT, VIDEO_WIDTH


def extract_script_lines(script_path) -> list[str]:
    content = Path(script_path).read_text(encoding="utf-8")
    match = re.search(r"##\s*Script\s*\n+([\s\S]+?)(?:\n##|\Z)", content, re.IGNORECASE)
    text = match.group(1).strip() if match else content
    lines = []
    for raw in text.split("\n"):
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines or [text[:120]]


def _hex(c: str) -> tuple[int, int, int]:
    return tuple(int(c.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            from pathlib import Path

            if Path(path).exists():
                return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sky_gradient(draw: ImageDraw.ImageDraw, top: str, bottom: str) -> None:
    t, b = _hex(top), _hex(bottom)
    for y in range(VIDEO_HEIGHT):
        r = y / max(VIDEO_HEIGHT - 1, 1)
        color = tuple(int(t[i] + (b[i] - t[i]) * r) for i in range(3))
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=color)


def draw_cloud(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, drift: int) -> None:
    x += drift
    r = int(40 * scale)
    for dx, dy, rad in [(0, 0, r), (-r, 10, int(r * 0.7)), (r, 8, int(r * 0.8)), (-r // 2, -8, int(r * 0.55))]:
        draw.ellipse((x + dx - rad, y + dy - rad, x + dx + rad, y + dy + rad), fill=(255, 255, 255))


def draw_hills(draw: ImageDraw.ImageDraw, base_y: int, color: str) -> None:
    c = _hex(color)
    points = [(0, VIDEO_HEIGHT), (0, base_y)]
    for x in range(0, VIDEO_WIDTH + 1, 80):
        points.append((x, base_y + int(35 * math.sin(x / 120))))
    points += [(VIDEO_WIDTH, base_y), (VIDEO_WIDTH, VIDEO_HEIGHT)]
    draw.polygon(points, fill=c)


def draw_sun(draw: ImageDraw.ImageDraw, x: int, y: int, pulse: float) -> None:
    r = int(70 + 8 * math.sin(pulse))
    draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 220, 80))
    for i in range(8):
        ang = i * math.pi / 4 + pulse * 0.2
        x1 = x + int(math.cos(ang) * (r + 12))
        y1 = y + int(math.sin(ang) * (r + 12))
        x2 = x + int(math.cos(ang) * (r + 28))
        y2 = y + int(math.sin(ang) * (r + 28))
        draw.line([(x1, y1), (x2, y2)], fill=(255, 230, 120), width=6)


def draw_gate(draw: ImageDraw.ImageDraw, x: int, y: int, open_amt: float) -> None:
    w, h = 280, 360
    draw.rectangle((x - 8, y - h, x + w + 8, y + 12), fill=(120, 78, 42))
    left_angle = -18 * open_amt
    right_angle = 18 * open_amt
    draw.rectangle((x, y - h + 20, x + w // 2 - 6, y), fill=(160, 110, 65), outline=(90, 55, 30), width=4)
    draw.rectangle((x + w // 2 + 6, y - h + 20, x + w, y), fill=(160, 110, 65), outline=(90, 55, 30), width=4)
    draw.arc((x - 20, y - h - 10, x + w + 20, y + 40), 200, 340, fill=(90, 55, 30), width=8)
    draw.text((x + w // 2 - 40, y - h // 2), "GARDEN", fill=(255, 240, 200), font=load_font(28))


def draw_flowers(draw: ImageDraw.ImageDraw, base_y: int, frame: int) -> None:
    rng = random.Random(42)
    colors = ["#FF6B9D", "#FFD166", "#9B5DE5", "#00BBF9", "#F15BB5"]
    for i in range(18):
        x = 60 + i * 55 + int(6 * math.sin(frame / 10 + i))
        y = base_y - 20 + rng.randint(-8, 8)
        col = _hex(colors[i % len(colors)])
        draw.line([(x, y), (x, y - 35)], fill=(45, 140, 55), width=4)
        draw.ellipse((x - 12, y - 48, x + 12, y - 24), fill=col)


def draw_bunny(draw: ImageDraw.ImageDraw, cx: int, cy: int, pose: str, bounce: float) -> None:
    cy += int(bounce)
    body = (245, 245, 250)
    ear_h = 95 if pose != "hop" else 110
    # ears
    draw.ellipse((cx - 48, cy - ear_h - 40, cx - 8, cy - 20), fill=body, outline=(210, 210, 220), width=3)
    draw.ellipse((cx + 8, cy - ear_h - 35, cx + 48, cy - 18), fill=body, outline=(210, 210, 220), width=3)
    draw.ellipse((cx - 38, cy - ear_h - 25, cx - 18, cy - 35), fill=(255, 190, 200))
    draw.ellipse((cx + 18, cy - ear_h - 22, cx + 38, cy - 32), fill=(255, 190, 200))
    # body
    draw.ellipse((cx - 70, cy - 30, cx + 70, cy + 110), fill=body, outline=(210, 210, 220), width=3)
    # head
    draw.ellipse((cx - 58, cy - 95, cx + 58, cy + 15), fill=body, outline=(210, 210, 220), width=3)
    # face
    eye_y = cy - 35
    if pose == "scared":
        draw.ellipse((cx - 28, eye_y - 8, cx - 10, eye_y + 10), fill=(40, 40, 60))
        draw.ellipse((cx + 10, eye_y - 8, cx + 28, eye_y + 10), fill=(40, 40, 60))
        draw.arc((cx - 18, cy - 5, cx + 18, cy + 18), 200, 340, fill=(80, 80, 100), width=3)
    elif pose == "happy":
        draw.ellipse((cx - 28, eye_y - 10, cx - 10, eye_y + 6), fill=(40, 40, 60))
        draw.ellipse((cx + 10, eye_y - 10, cx + 28, eye_y + 6), fill=(40, 40, 60))
        draw.arc((cx - 22, cy - 8, cx + 22, cy + 20), 10, 170, fill=(220, 80, 100), width=4)
        draw.ellipse((cx - 40, cy - 5, cx - 24, cy + 10), fill=(255, 170, 180))
        draw.ellipse((cx + 24, cy - 5, cx + 40, cy + 10), fill=(255, 170, 180))
    else:
        draw.ellipse((cx - 28, eye_y - 8, cx - 10, eye_y + 8), fill=(40, 40, 60))
        draw.ellipse((cx + 10, eye_y - 8, cx + 28, eye_y + 8), fill=(40, 40, 60))
        draw.ellipse((cx - 8, cy - 2, cx + 8, cy + 10), fill=(255, 150, 160))
    # feet hop offset
    if pose == "hop":
        draw.ellipse((cx - 55, cy + 85, cx - 15, cy + 125), fill=body, outline=(210, 210, 220), width=2)
        draw.ellipse((cx + 15, cy + 70, cx + 55, cy + 110), fill=body, outline=(210, 210, 220), width=2)
    else:
        draw.ellipse((cx - 50, cy + 95, cx - 18, cy + 125), fill=body, outline=(210, 210, 220), width=2)
        draw.ellipse((cx + 18, cy + 95, cx + 50, cy + 125), fill=body, outline=(210, 210, 220), width=2)


def draw_friends(draw: ImageDraw.ImageDraw, frame: int) -> None:
    t = frame / 30
    # small bird
    bx = 820 + int(10 * math.sin(t))
    by = 520 + int(8 * math.cos(t * 1.3))
    draw.ellipse((bx - 18, by - 12, bx + 18, by + 12), fill=(90, 180, 255))
    draw.polygon([(bx + 16, by), (bx + 34, by - 4), (bx + 34, by + 4)], fill=(255, 180, 60))


def draw_sparkles(draw: ImageDraw.ImageDraw, frame: int) -> None:
    rng = random.Random(7)
    for i in range(20):
        x = rng.randint(40, VIDEO_WIDTH - 40)
        y = rng.randint(80, VIDEO_HEIGHT - 300)
        s = 3 + (i + frame) % 5
        alpha = int(180 + 70 * math.sin((frame + i * 11) / 8))
        col = (255, 255, min(255, alpha))
        draw.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=col)


def pose_for_line(idx: int, total: int) -> str:
    if idx == 0:
        return "scared"
    if idx >= total - 2:
        return "happy"
    if idx % 2 == 1:
        return "hop"
    return "idle"


def scene_palette(idx: int) -> tuple[str, str, str]:
    palettes = [
        ("#89CFF0", "#FFE5F1", "#7BC96F"),
        ("#A8D8FF", "#FFF4C2", "#8FD694"),
        ("#B8E1FF", "#FFD6E8", "#9AD9A0"),
        ("#FFE9A8", "#FFF8DC", "#98D98E"),
    ]
    return palettes[idx % len(palettes)]


def render_cartoon_frame(line: str, line_idx: int, total_lines: int, frame_idx: int, frames_in_scene: int) -> Image.Image:
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    sky_top, sky_bottom, hill = scene_palette(line_idx)
    sky_gradient(draw, sky_top, sky_bottom)
    t = frame_idx / max(frames_in_scene, 1)
    drift = int(12 * math.sin(frame_idx / 18))

    draw_cloud(draw, 180, 180, 1.2, drift)
    draw_cloud(draw, 620, 140, 1.5, -drift)
    draw_cloud(draw, 900, 220, 1.0, drift // 2)

    if line_idx >= total_lines - 2:
        draw_sun(draw, 860, 200, frame_idx / 6)

    base_y = 1320 if line_idx < total_lines - 1 else 1280
    draw_hills(draw, base_y, hill)
    draw_flowers(draw, base_y, frame_idx)

    gate_open = min(1.0, line_idx / max(total_lines - 2, 1))
    if line_idx < total_lines - 1:
        draw_gate(draw, 700, base_y, gate_open)

    pose = pose_for_line(line_idx, total_lines)
    hop = 0
    if pose == "hop":
        hop = -abs(int(35 * math.sin(frame_idx / 4)))
    elif pose == "happy":
        hop = -abs(int(12 * math.sin(frame_idx / 6)))
    elif pose == "scared":
        hop = int(4 * math.sin(frame_idx / 10))

    bunny_x = 380 + int(180 * min(1.0, line_idx / max(total_lines - 2, 1)))
    if pose == "hop":
        bunny_x += int(20 * math.sin(frame_idx / 3))
    draw_bunny(draw, bunny_x, base_y - 40, pose, hop)

    if line_idx >= total_lines - 2:
        draw_friends(draw, frame_idx)

    draw_sparkles(draw, frame_idx)

    # subtitle bar
    bar_h = 220
    overlay = Image.new("RGBA", (VIDEO_WIDTH, bar_h), (20, 20, 60, 170))
    img.paste(overlay, (0, VIDEO_HEIGHT - bar_h), overlay)
    draw = ImageDraw.Draw(img)
    font = load_font(46)
    words = line.split()
    if len(words) > 8:
        line = " ".join(words[:8]) + "..."
    bbox = draw.textbbox((0, 0), line, font=font)
    tx = (VIDEO_WIDTH - (bbox[2] - bbox[0])) // 2
    ty = VIDEO_HEIGHT - bar_h + (bar_h - (bbox[3] - bbox[1])) // 2
    draw.text((tx + 2, ty + 2), line, font=font, fill=(0, 0, 0))
    draw.text((tx, ty), line, font=font, fill=(255, 255, 255))

    return img
