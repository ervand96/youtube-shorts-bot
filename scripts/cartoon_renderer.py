"""NuNu TV / Cocomelon-style 2D renderer with toddler characters and rich scenes."""

from __future__ import annotations

import hashlib
import math
import re
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config.settings import VIDEO_HEIGHT, VIDEO_WIDTH

CATEGORY_SCENES: dict[str, list[str]] = {
    "nursery": ("bus", "rainbow_road", "song_circle"),
    "bedtime": ("bedroom_night", "moon_stars", "sleepy_meadow"),
    "learning": ("classroom", "color_blocks", "counting_garden"),
    "moral": ("picnic", "sharing_table", "friends_meadow"),
    "animals": ("farm_barn", "animal_band", "meadow_animals"),
}
DEFAULT_SCENES = ("meadow", "playground", "party")


@dataclass
class VideoTheme:
    category: str
    palette_idx: int
    scenes: tuple[str, ...]
    bus_color: tuple[int, int, int]
    accent: tuple[int, int, int]
    night_mode: bool


def extract_script_lines(script_path) -> list[str]:
    content = Path(script_path).read_text(encoding="utf-8")
    match = re.search(r"##\s*Script\s*\n+([\s\S]+?)(?:\n##|\Z)", content, re.IGNORECASE)
    text = match.group(1).strip() if match else content
    lines = [ln.strip() for ln in text.split("\n") if ln.strip() and not ln.startswith("#")]
    return lines or [text[:120]]


def parse_script_category(script_path: Path) -> str:
    content = script_path.read_text(encoding="utf-8")
    match = re.search(r"Category:\s*(\w+)", content, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    lowered = content.lower()
    for keyword, category in (
        ("farm", "animals"),
        ("animal", "animals"),
        ("bedtime", "bedtime"),
        ("sleep", "bedtime"),
        ("color", "learning"),
        ("number", "learning"),
        ("abc", "learning"),
        ("sharing", "moral"),
        ("moral", "moral"),
        ("bus", "nursery"),
        ("nursery", "nursery"),
        ("rhyme", "nursery"),
    ):
        if keyword in lowered:
            return category
    return "nursery"


def build_video_theme(script_path: Path) -> VideoTheme:
    category = parse_script_category(script_path)
    digest = int(hashlib.md5(str(script_path).encode()).hexdigest()[:8], 16)
    scenes = CATEGORY_SCENES.get(category, DEFAULT_SCENES)
    palette_idx = digest % 4
    bus_colors = (
        (255, 210, 0),
        (255, 120, 80),
        (80, 180, 255),
        (180, 100, 255),
    )
    accents = (
        (255, 90, 120),
        (90, 170, 255),
        (120, 200, 90),
        (255, 170, 60),
    )
    return VideoTheme(
        category=category,
        palette_idx=palette_idx,
        scenes=scenes,
        bus_color=bus_colors[palette_idx],
        accent=accents[palette_idx],
        night_mode=category == "bedtime",
    )


def pick_scene(theme: VideoTheme, line: str, line_idx: int) -> str:
    lowered = line.lower()
    keyword_map = (
        (("cow", "moo", "duck", "quack", "farm", "pig", "sheep"), "animal_band"),
        (("star", "sleep", "dream", "moon", "bed"), "moon_stars"),
        (("red", "blue", "yellow", "green", "color", "count", "number"), "color_blocks"),
        (("share", "picnic", "muffin", "caring"), "picnic"),
        (("bus", "wheel", "wiper", "round"), "bus"),
        (("rainbow",), "rainbow_road"),
    )
    for keywords, scene in keyword_map:
        if any(word in lowered for word in keywords):
            return scene
    return theme.scenes[line_idx % len(theme.scenes)]


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


def draw_yellow_bus(draw: ImageDraw.ImageDraw, base_y: int, frame: int, body_color: tuple[int, int, int] = (255, 210, 0)) -> None:
    bx, by = 120, base_y - 280
    wobble = int(4 * math.sin(frame / 6))
    outline = tuple(max(0, c - 50) for c in body_color)
    draw.rounded_rectangle((bx, by + wobble, bx + 520, by + 220 + wobble), radius=40, fill=body_color, outline=outline, width=6)
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


def draw_bedroom_bg(draw: ImageDraw.ImageDraw, base_y: int, night: bool = False) -> None:
    wall = (55, 45, 95) if night else (255, 230, 245)
    bed = (120, 90, 200) if night else (180, 140, 255)
    draw.rectangle((0, 0, VIDEO_WIDTH, base_y), fill=wall)
    draw.rounded_rectangle((100, base_y - 320, 500, base_y - 40), radius=30, fill=bed)
    draw.rectangle((100, base_y - 120, 500, base_y - 40), fill=(255, 255, 255))
    lamp = (255, 245, 180) if night else (255, 245, 180)
    draw.ellipse((600, base_y - 350, 750, base_y - 200), fill=lamp)


def draw_moon(draw: ImageDraw.ImageDraw, frame: int) -> None:
    glow = int(8 * math.sin(frame / 15))
    draw.ellipse((760 + glow, 120, 940 + glow, 300), fill=(255, 245, 170), outline=(255, 230, 120), width=4)


def draw_rainbow_road(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    colors = ("#FF595E", "#FFCA3A", "#8AC926", "#1982C4", "#6A4C93")
    for i, color in enumerate(colors):
        y = base_y - 40 - i * 18
        draw.rounded_rectangle((180, y, 900, y + 14), radius=8, fill=_hex(color))


def draw_color_blocks(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    blocks = ((255, 80, 80), (80, 140, 255), (255, 220, 60), (90, 200, 90))
    labels = ("1", "2", "3", "4", "5")
    for i, color in enumerate(blocks):
        x = 140 + i * 210
        draw.rounded_rectangle((x, base_y - 360, x + 170, base_y - 120), radius=24, fill=color, outline=(255, 255, 255), width=5)
        draw.text((x + 65, base_y - 290), labels[i], font=load_font(72), fill=(255, 255, 255))
    draw.rounded_rectangle((120, base_y - 500, 960, base_y - 80), radius=30, outline=(255, 255, 255), width=6)


def draw_farm_barn(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    draw.polygon([(120, base_y - 40), (120, base_y - 280), (280, base_y - 360), (440, base_y - 280), (440, base_y - 40)], fill=(190, 60, 60))
    draw.rectangle((170, base_y - 180, 390, base_y - 40), fill=(120, 70, 40))
    draw.polygon([(500, base_y - 40), (500, base_y - 220), (620, base_y - 300), (740, base_y - 220), (740, base_y - 40)], fill=(220, 90, 70))


def draw_farm_animal(draw: ImageDraw.ImageDraw, cx: int, cy: int, kind: str, frame: int) -> None:
    bounce = int(8 * math.sin(frame / 4 + cx))
    cy += bounce
    if kind == "cow":
        glossy_ellipse(draw, (cx - 70, cy - 40, cx + 70, cy + 90), (70, 70, 80), (40, 40, 50))
        draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(255, 230, 230))
        draw.ellipse((cx - 55, cy - 70, cx - 15, cy - 10), fill=(70, 70, 80))
        draw.ellipse((cx + 15, cy - 70, cx + 55, cy - 10), fill=(70, 70, 80))
    elif kind == "duck":
        glossy_ellipse(draw, (cx - 55, cy - 10, cx + 55, cy + 70), (255, 220, 60), (220, 170, 30))
        draw.ellipse((cx - 35, cy - 45, cx + 35, cy + 5), fill=(255, 220, 60))
        draw.polygon([(cx + 30, cy - 10), (cx + 70, cy - 5), (cx + 30, cy + 5)], fill=(255, 140, 40))
    elif kind == "sheep":
        for dx, dy in ((-30, -20), (0, -35), (30, -20), (-15, 0), (15, 0)):
            draw.ellipse((cx + dx - 28, cy + dy - 28, cx + dx + 28, cy + dy + 28), fill=(245, 245, 250))
        draw.ellipse((cx - 22, cy - 10, cx + 22, cy + 30), fill=(30, 30, 40))
    else:
        glossy_ellipse(draw, (cx - 60, cy - 20, cx + 60, cy + 80), (255, 170, 190), (220, 120, 140))
        draw.ellipse((cx - 20, cy - 15, cx + 20, cy + 15), fill=(255, 210, 220))
        draw.ellipse((cx - 25, cy - 55, cx - 5, cy - 15), fill=(255, 170, 190))
        draw.ellipse((cx + 5, cy - 55, cx + 25, cy - 15), fill=(255, 170, 190))


def draw_picnic_scene(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    draw.rounded_rectangle((220, base_y - 70, 860, base_y - 10), radius=20, fill=(255, 120, 140))
    draw.ellipse((280, base_y - 120, 360, base_y - 40), fill=(180, 110, 70))
    draw.ellipse((420, base_y - 110, 500, base_y - 30), fill=(255, 210, 120))
    draw.ellipse((560, base_y - 115, 640, base_y - 35), fill=(255, 180, 200))
    draw.ellipse((700, base_y - 105, 780, base_y - 25), fill=(140, 210, 120))


def draw_sky_scene(draw: ImageDraw.ImageDraw, palette_idx: int, frame: int, night: bool = False) -> int:
    if night:
        palettes = [
            ("#1B1F3B", "#3D2C5E", "#2D4A3E"),
            ("#0F172A", "#312E81", "#14532D"),
        ]
    else:
        palettes = [
            ("#5BC8FF", "#B8E8FF", "#6AD66A"),
            ("#89CFF0", "#FFE5B4", "#7ED957"),
            ("#FFB6C1", "#FFF0F5", "#98D98E"),
            ("#FFD93D", "#FFF8DC", "#6BCB77"),
        ]
    top, mid, hill = palettes[palette_idx % len(palettes)]
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


def render_scene(
    draw: ImageDraw.ImageDraw,
    scene: str,
    base_y: int,
    frame_idx: int,
    theme: VideoTheme,
) -> None:
    if scene == "bus":
        draw_yellow_bus(draw, base_y, frame_idx, theme.bus_color)
        draw_toddler(draw, 720, base_y - 60, frame_idx, "blonde")
        draw_bunny_friend(draw, 900, base_y - 30, frame_idx)
    elif scene == "rainbow_road":
        draw_rainbow_road(draw, base_y)
        draw_yellow_bus(draw, base_y, frame_idx, theme.bus_color)
        draw_bunny_friend(draw, 820, base_y - 40, frame_idx)
    elif scene == "song_circle":
        draw.ellipse((360, base_y - 220, 720, base_y + 20), fill=(255, 240, 120), outline=(255, 200, 60), width=5)
        draw_toddler(draw, 540, base_y - 80, frame_idx, "brown")
        draw_bunny_friend(draw, 700, base_y - 50, frame_idx)
    elif scene in {"bedroom_night", "moon_stars", "sleepy_meadow"}:
        draw_bedroom_bg(draw, base_y, night=True)
        if scene != "sleepy_meadow":
            draw_moon(draw, frame_idx)
        draw_toddler(draw, 540, base_y - 80, frame_idx, "blonde")
        draw_bunny_friend(draw, 750, base_y - 40, frame_idx)
    elif scene in {"classroom", "color_blocks", "counting_garden"}:
        draw.rounded_rectangle((80, base_y - 420, 1000, base_y - 60), radius=30, fill=(255, 245, 220), outline=(220, 200, 160), width=6)
        draw_color_blocks(draw, base_y)
        draw_toddler(draw, 500, base_y - 50, frame_idx, "blonde")
    elif scene in {"picnic", "sharing_table", "friends_meadow"}:
        draw_picnic_scene(draw, base_y)
        draw_toddler(draw, 500, base_y - 90, frame_idx, "brown")
        draw_bunny_friend(draw, 700, base_y - 60, frame_idx)
    elif scene in {"farm_barn", "animal_band", "meadow_animals"}:
        draw_farm_barn(draw, base_y)
        draw_farm_animal(draw, 300, base_y - 40, "cow", frame_idx)
        draw_farm_animal(draw, 520, base_y - 20, "duck", frame_idx)
        draw_farm_animal(draw, 720, base_y - 30, "sheep", frame_idx)
        draw_farm_animal(draw, 900, base_y - 10, "pig", frame_idx)
        draw_bunny_friend(draw, 560, base_y - 80, frame_idx)
    elif scene == "playground":
        draw_playground(draw, base_y)
        draw_toddler(draw, 480, base_y - 50, frame_idx, "brown")
        draw_bunny_friend(draw, 650, base_y - 20, frame_idx)
    else:
        draw.ellipse((750, 180, 950, 380), fill=(255, 230, 100))
        draw_toddler(draw, 500, base_y - 50, frame_idx, "blonde")
        draw_bunny_friend(draw, 300, base_y - 30, frame_idx)


def render_cartoon_frame(
    line: str,
    line_idx: int,
    total_lines: int,
    frame_idx: int,
    frames_in_scene: int,
    theme: VideoTheme,
) -> Image.Image:
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    scene = pick_scene(theme, line, line_idx)
    base_y = draw_sky_scene(draw, theme.palette_idx, frame_idx, night=theme.night_mode or scene in {"bedroom_night", "moon_stars"})
    if theme.night_mode or scene in {"bedroom_night", "moon_stars", "sleepy_meadow"}:
        draw_stars(draw, frame_idx)
    render_scene(draw, scene, base_y, frame_idx, theme)

    font = load_font(44)
    words = line.split()
    caption = " ".join(words[:9]) + ("..." if len(words) > 9 else "")
    pad = 28
    bbox = draw.textbbox((0, 0), caption, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px = (VIDEO_WIDTH - tw) // 2 - pad
    py = VIDEO_HEIGHT - 200
    accent = theme.accent
    shadow = tuple(max(0, c - 70) for c in accent)
    draw.rounded_rectangle((px, py, px + tw + pad * 2, py + th + pad * 2), radius=30, fill=accent)
    draw.text((px + pad + 2, py + pad + 2), caption, font=font, fill=shadow)
    draw.text((px + pad, py + pad), caption, font=font, fill=(255, 255, 255))

    return img
