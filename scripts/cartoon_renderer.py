"""NuNu TV / Cocomelon-style 2D renderer — professional parallax scenes with Benny."""

from __future__ import annotations

import math
import re
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config.settings import VIDEO_HEIGHT, VIDEO_WIDTH
from scripts.motion_effects import (
    apply_shake,
    draw_confetti,
    hook_burst,
    pulse_scale,
    shake_offset,
)

CATEGORY_SCENES: dict[str, tuple[str, ...]] = {
    "nursery": ("bus", "rainbow_road", "song_circle"),
    "bedtime": ("moon_stars", "bedroom_night", "sleepy_meadow"),
    "learning": ("color_blocks", "classroom", "counting_garden"),
    "moral": ("picnic", "sharing_table", "friends_meadow"),
    "animals": ("animal_band", "farm_barn", "meadow_animals"),
}
CATEGORY_PALETTE: dict[str, int] = {
    "nursery": 0,
    "animals": 1,
    "learning": 2,
    "moral": 3,
    "bedtime": 4,
}
CATEGORY_ACCENTS: dict[str, tuple[int, int, int]] = {
    "nursery": (46, 175, 80),
    "bedtime": (90, 110, 200),
    "learning": (30, 136, 229),
    "moral": (233, 80, 120),
    "animals": (76, 175, 80),
}
CATEGORY_BUS_COLORS: dict[str, tuple[int, int, int]] = {
    "nursery": (255, 210, 0),
    "animals": (255, 140, 60),
    "learning": (80, 180, 255),
    "moral": (180, 100, 255),
    "bedtime": (255, 200, 120),
}
DEFAULT_SCENES = ("meadow", "playground", "party")

SKY_PALETTES = [
    ("#4FC3F7", "#B3E5FC", "#81C784", "#66BB6A"),  # nursery
    ("#64B5F6", "#FFF9C4", "#AED581", "#7CB342"),  # animals
    ("#90CAF9", "#FFF8E1", "#A5D6A7", "#4CAF50"),  # learning
    ("#F48FB1", "#FCE4EC", "#A5D6A7", "#66BB6A"),  # moral
    ("#1A237E", "#3949AB", "#2E7D32", "#1B5E20"),  # bedtime
]
NIGHT_SKY = ("#0D1B2A", "#1B263B", "#2D6A4F", "#1B4332")

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


@dataclass
class VideoTheme:
    category: str
    palette_idx: int
    scenes: tuple[str, ...]
    bus_color: tuple[int, int, int]
    accent: tuple[int, int, int]
    night_mode: bool


@dataclass
class SceneContext:
    frame_idx: int
    line_progress: float
    parallax: float
    theme: VideoTheme
    global_frame: int = 0
    energetic: bool = False


def line_is_energetic(line: str) -> bool:
    upper = line.upper()
    return "!" in line or "CLAP" in upper or "STOMP" in upper or "JUMP" in upper


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


def _parse_slot(script_path: Path) -> int:
    match = re.search(r"-(\d+)-topic\.md$", script_path.name)
    return int(match.group(1)) if match else 1


def build_video_theme(script_path: Path) -> VideoTheme:
    category = parse_script_category(script_path)
    slot = _parse_slot(script_path)
    scenes = CATEGORY_SCENES.get(category, DEFAULT_SCENES)
    palette_idx = CATEGORY_PALETTE.get(category, slot % 4)
    return VideoTheme(
        category=category,
        palette_idx=palette_idx,
        scenes=scenes,
        bus_color=CATEGORY_BUS_COLORS.get(category, (255, 210, 0)),
        accent=CATEGORY_ACCENTS.get(category, (255, 90, 120)),
        night_mode=category == "bedtime",
    )


def pick_scene(theme: VideoTheme, line: str, line_idx: int) -> str:
    base = theme.scenes[line_idx % len(theme.scenes)]
    lowered = line.lower()
    if theme.category == "animals" and any(w in lowered for w in ("cow", "moo", "duck", "quack", "pig", "sheep", "farm")):
        return "animal_band"
    if theme.category == "bedtime" and any(w in lowered for w in ("star", "sleep", "dream", "moon")):
        return "moon_stars"
    if theme.category == "learning" and any(w in lowered for w in ("abc", "letter", "color", "number", "count")):
        return "color_blocks"
    if theme.category == "moral" and any(w in lowered for w in ("share", "kind", "caring", "picnic")):
        return "picnic"
    if theme.category == "nursery" and line_idx == 0:
        return theme.scenes[0]
    return base


def _hex(c: str) -> tuple[int, int, int]:
    return tuple(int(c.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _lerp_rgb(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t), _lerp(c1[2], c2[2], t))


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def glossy_ellipse(draw: ImageDraw.ImageDraw, box: tuple, fill: tuple, outline: tuple | None = None, width: int = 3) -> None:
    draw.ellipse(box, fill=fill, outline=outline, width=width)
    x0, y0, x1, y1 = box
    hw, hh = max((x1 - x0) // 5, 4), max((y1 - y0) // 5, 4)
    highlight = tuple(min(255, c + 60) for c in fill)
    draw.ellipse((x0 + hw, y0 + hh, x0 + hw * 2, y0 + hh * 2), fill=highlight)


def draw_soft_shadow(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int) -> None:
    draw.ellipse((cx - rx, cy - ry // 3, cx + rx, cy + ry), fill=(0, 0, 0, 40))


def draw_gradient_sky(img: Image.Image, palette: tuple[str, ...], night: bool = False) -> None:
    colors = NIGHT_SKY if night else palette
    top, mid, hill1, hill2 = (_hex(c) for c in colors)
    draw = ImageDraw.Draw(img)
    horizon = int(VIDEO_HEIGHT * 0.55)
    for y in range(horizon):
        t = y / max(horizon - 1, 1)
        color = _lerp_rgb(top, mid, t)
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=color)
    for y in range(horizon, VIDEO_HEIGHT):
        t = (y - horizon) / max(VIDEO_HEIGHT - horizon - 1, 1)
        color = _lerp_rgb(mid, hill1, min(t * 1.5, 1.0))
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=color)
    base_y = int(VIDEO_HEIGHT * 0.72)
    draw.polygon(
        [(0, base_y + 40), (VIDEO_WIDTH, base_y), (VIDEO_WIDTH, VIDEO_HEIGHT), (0, VIDEO_HEIGHT)],
        fill=hill2,
    )
    draw.polygon(
        [(0, base_y + 80), (VIDEO_WIDTH, base_y + 50), (VIDEO_WIDTH, VIDEO_HEIGHT), (0, VIDEO_HEIGHT)],
        fill=hill1,
    )


def draw_balloons(img: Image.Image, frame: int, parallax: float) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    colors = ((255, 90, 120), (80, 170, 255), (255, 210, 60), (140, 220, 100))
    for i, color in enumerate(colors):
        bx = int(140 + i * 220 + parallax * 0.4 + 25 * math.sin(frame / 20 + i))
        by = int(320 + 30 * math.sin(frame / 12 + i * 1.5))
        draw.line([(bx, by + 55), (bx + int(8 * math.sin(frame / 15)), by + 200)], fill=(80, 80, 90, 180), width=3)
        draw.ellipse((bx - 28, by - 10, bx + 28, by + 55), fill=(*color, 230))
        draw.polygon([(bx - 6, by + 52), (bx + 6, by + 52), (bx, by + 64)], fill=(*color, 230))
    img.paste(layer, (0, 0), layer)


def draw_birds(img: Image.Image, frame: int, parallax: float) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for i in range(4):
        t = frame / 25 + i * 1.8
        x = int((200 + i * 200 + parallax * 0.5 + frame * 4) % (VIDEO_WIDTH + 100) - 50)
        y = int(140 + i * 35 + 20 * math.sin(t))
        wing = int(8 + 6 * math.sin(frame / 3 + i))
        draw.arc((x - wing, y - 6, x, y + 6), 0, 180, fill=(60, 60, 80, 200), width=3)
        draw.arc((x, y - 6, x + wing, y + 6), 180, 360, fill=(60, 60, 80, 200), width=3)
    img.paste(layer, (0, 0), layer)


def draw_clouds(img: Image.Image, frame: int, parallax: float, night: bool = False) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cloud_color = (255, 255, 255, 200) if not night else (200, 210, 255, 80)
    drift = int(parallax * 1.2 + frame * 1.5 + 20 * math.sin(frame / 45))
    clouds = [
        (120 + drift, 180, 1.0),
        (480 + int(drift * 0.7), 120, 1.3),
        (780 + int(drift * 0.5), 240, 0.9),
        (950 + drift, 160, 1.1),
    ]
    for cx, cy, scale in clouds:
        for dx, dy, rad in [(0, 0, int(50 * scale)), (-int(40 * scale), 10, int(35 * scale)), (int(42 * scale), 8, int(38 * scale))]:
            draw.ellipse(
                (cx + dx - rad, cy + dy - rad, cx + dx + rad, cy + dy + rad),
                fill=cloud_color,
            )
    img.paste(layer, (0, 0), layer)


def draw_sun(img: Image.Image, frame: int) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    pulse = 1.0 + 0.04 * math.sin(frame / 12)
    cx, cy = 880, 220
    glow_r = int(130 * pulse)
    for r, alpha in [(glow_r, 30), (int(100 * pulse), 50), (int(70 * pulse), 90)]:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 230, 80, alpha))
    draw.ellipse((cx - 55, cy - 55, cx + 55, cy + 55), fill=(255, 220, 60, 255))
    for angle in range(0, 360, 30):
        rad = math.radians(angle + frame * 0.5)
        x1 = cx + int(65 * math.cos(rad))
        y1 = cy + int(65 * math.sin(rad))
        x2 = cx + int(95 * math.cos(rad))
        y2 = cy + int(95 * math.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(255, 240, 120, 180), width=6)
    img.paste(layer, (0, 0), layer)


def draw_moon_glow(img: Image.Image, frame: int) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    glow = int(6 * math.sin(frame / 15))
    cx, cy = 850 + glow, 200
    draw.ellipse((cx - 100, cy - 100, cx + 100, cy + 100), fill=(255, 245, 170, 40))
    draw.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), fill=(255, 248, 200, 255), outline=(255, 230, 120, 200), width=4)
    img.paste(layer, (0, 0), layer)


def draw_stars(img: Image.Image, frame: int) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rng = random.Random(42)
    for i in range(40):
        x, y = rng.randint(20, VIDEO_WIDTH - 20), rng.randint(30, 600)
        twinkle = (math.sin(frame / 8 + i * 1.7) + 1) / 2
        alpha = int(80 + 175 * twinkle)
        s = 3 + (i % 3)
        draw.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=(255, 255, 220, alpha))
    img.paste(layer, (0, 0), layer)


def draw_foreground_flowers(draw: ImageDraw.ImageDraw, base_y: int, frame: int, accent: tuple[int, int, int]) -> None:
    colors = (accent, (255, 200, 80), (255, 120, 150), (180, 120, 255))
    rng = random.Random(7)
    for i in range(18):
        x = 40 + i * 58 + rng.randint(-10, 10)
        sway = int(6 * math.sin(frame / 10 + i * 0.8))
        stem_h = 50 + rng.randint(0, 30)
        y = base_y + 30
        draw.line([(x, y), (x + sway, y - stem_h)], fill=(60, 140, 60), width=4)
        petal_c = colors[i % len(colors)]
        draw.ellipse((x + sway - 12, y - stem_h - 20, x + sway + 12, y - stem_h + 4), fill=petal_c)
        draw.ellipse((x + sway - 4, y - stem_h - 12, x + sway + 4, y - stem_h - 4), fill=(255, 230, 80))


def draw_sparkles(img: Image.Image, frame: int, count: int = 12) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rng = random.Random(123)
    for i in range(count):
        x = rng.randint(100, VIDEO_WIDTH - 100)
        y = rng.randint(300, int(VIDEO_HEIGHT * 0.65))
        phase = frame / 6 + i * 2.1
        if math.sin(phase) > 0.3:
            s = int(4 + 3 * math.sin(phase))
            draw.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=(255, 255, 255, 200))
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 200, 255))
    img.paste(layer, (0, 0), layer)


def draw_benny(draw: ImageDraw.ImageDraw, cx: int, cy: int, ctx: SceneContext) -> None:
    """Benny — consistent channel mascot with bounce, blink, and wave."""
    frame = ctx.frame_idx
    bounce = int(12 * math.sin(frame / 5))
    cy += bounce
    skin = (255, 218, 185)
    hair_color = (255, 200, 60)
    overalls = (50, 130, 230)
    shirt = (255, 90, 90)

    draw_soft_shadow(draw, cx, cy + 195, 80, 22)

    # walk cycle — legs alternate every few frames
    step = math.sin(frame / 4)
    left_lift = int(18 * max(0, step))
    right_lift = int(18 * max(0, -step))
    legs = ((cx - 35, left_lift), (cx + 15, right_lift))
    for lx, lift in legs:
        draw.rounded_rectangle((lx, cy + 155 - lift, lx + 40, cy + 210 - lift), radius=12, fill=overalls)
        draw.rounded_rectangle((lx - 4, cy + 200 - lift, lx + 44, cy + 225 - lift), radius=10, fill=(220, 50, 50))
    # sideways drift while walking
    cx += int(25 * math.sin(frame / 8))

    # body / overalls
    draw.rounded_rectangle((cx - 78, cy + 35, cx + 78, cy + 175), radius=35, fill=overalls, outline=(30, 90, 180), width=3)
    draw.rounded_rectangle((cx - 55, cy + 50, cx + 55, cy + 120), radius=20, fill=shirt)
    # straps
    draw.rectangle((cx - 50, cy + 35, cx - 35, cy + 90), fill=overalls)
    draw.rectangle((cx + 35, cy + 35, cx + 50, cy + 90), fill=overalls)
    # button
    draw.ellipse((cx - 10, cy + 130, cx + 10, cy + 150), fill=(255, 220, 60))

    # head
    glossy_ellipse(draw, (cx - 98, cy - 125, cx + 98, cy + 65), skin, (230, 185, 155), width=4)
    # hair
    draw.ellipse((cx - 85, cy - 155, cx + 85, cy - 45), fill=hair_color)
    draw.ellipse((cx - 35, cy - 180, cx + 35, cy - 90), fill=hair_color)
    # rosy cheeks
    for cheek_x in (cx - 70, cx + 40):
        draw.ellipse((cheek_x, cy - 15, cheek_x + 30, cy + 15), fill=(255, 170, 160))

    blink = (frame // 18) % 14 == 0
    # eyes
    for ex in (cx - 45, cx + 12):
        draw.ellipse((ex, cy - 48, ex + 40, cy - 6), fill=(255, 255, 255), outline=(200, 200, 210), width=2)
        if blink:
            draw.line([(ex + 4, cy - 28), (ex + 36, cy - 28)], fill=(60, 40, 30), width=4)
        else:
            pupil_x = ex + 14 + int(4 * math.sin(frame / 10))
            draw.ellipse((pupil_x, cy - 35, pupil_x + 18, cy - 15), fill=(35, 35, 55))
            draw.ellipse((pupil_x + 5, cy - 32, pupil_x + 11, cy - 24), fill=(255, 255, 255))

    # lip-sync style mouth — opens on syllable rhythm
    syllable_beat = math.sin(frame / 3 + ctx.line_progress * 12) > 0.2
    mouth_open = bounce > 6 or syllable_beat or ctx.energetic
    if mouth_open:
        draw.ellipse((cx - 22, cy - 5, cx + 22, cy + 25), fill=(200, 80, 90))
        draw.ellipse((cx - 18, cy + 2, cx + 18, cy + 18), fill=(255, 150, 150))
    else:
        draw.arc((cx - 38, cy - 18, cx + 38, cy + 28), 20, 160, fill=(210, 90, 90), width=5)

    # waving arm
    arm_swing = int(30 * math.sin(frame / 4))
    draw.line([(cx + 75, cy + 65), (cx + 130, cy + 5 + arm_swing)], fill=skin, width=20)
    draw.ellipse((cx + 115, cy - 5 + arm_swing, cx + 145, cy + 25 + arm_swing), fill=skin)
    # other arm
    draw.line([(cx - 75, cy + 70), (cx - 110, cy + 110)], fill=skin, width=18)


def draw_bunny_friend(draw: ImageDraw.ImageDraw, cx: int, cy: int, ctx: SceneContext) -> None:
    frame = ctx.frame_idx
    hop = int(22 * math.sin(frame / 3))
    cy -= abs(hop)
    white = (252, 252, 255)
    draw_soft_shadow(draw, cx, cy + 88, 50, 14)
    glossy_ellipse(draw, (cx - 58, cy - 22, cx + 58, cy + 92), white, (210, 210, 225), width=3)
    glossy_ellipse(draw, (cx - 52, cy - 112, cx + 52, cy + 8), white, (210, 210, 225), width=3)
    ear_sway = int(5 * math.sin(frame / 7))
    draw.ellipse((cx - 38 + ear_sway, cy - 155, cx - 8 + ear_sway, cy - 62), fill=white, outline=(230, 220, 240), width=2)
    draw.ellipse((cx + 8 - ear_sway, cy - 155, cx + 38 - ear_sway, cy - 62), fill=white, outline=(230, 220, 240), width=2)
    draw.ellipse((cx - 12, cy - 95, cx + 2, cy - 70), fill=(255, 190, 200))
    draw.ellipse((cx + 2, cy - 95, cx + 16, cy - 70), fill=(255, 190, 200))
    for ex in (cx - 24, cx + 8):
        draw.ellipse((ex, cy - 38, ex + 18, cy - 18), fill=(40, 40, 60))
        draw.ellipse((ex + 4, cy - 34, ex + 9, cy - 27), fill=(255, 255, 255))
    nose_wiggle = int(2 * math.sin(frame / 5))
    draw.ellipse((cx - 6 + nose_wiggle, cy - 12, cx + 6 + nose_wiggle, cy + 2), fill=(255, 160, 180))


def draw_yellow_bus(draw: ImageDraw.ImageDraw, base_y: int, ctx: SceneContext, body_color: tuple[int, int, int]) -> None:
    frame = ctx.frame_idx
    parallax = ctx.parallax
    bx = 100 + int(parallax * 0.3)
    by = base_y - 290
    wobble = int(5 * math.sin(frame / 6))
    outline = tuple(max(0, c - 50) for c in body_color)
    draw.rounded_rectangle((bx, by + wobble, bx + 540, by + 230 + wobble), radius=42, fill=body_color, outline=outline, width=7)
    # shine stripe
    draw.rounded_rectangle((bx + 8, by + 15 + wobble, bx + 532, by + 45 + wobble), radius=10, fill=tuple(min(255, c + 40) for c in body_color))
    draw.rounded_rectangle((bx + 35, by + 45 + wobble, bx + 505, by + 155 + wobble), radius=22, fill=(170, 225, 255))
    for wx in (65, 210, 355):
        draw.rounded_rectangle((bx + wx, by + 58 + wobble, bx + wx + 115, by + 140 + wobble), radius=14, fill=(200, 240, 255))
        draw.line([(bx + wx + 18, by + 65 + wobble), (bx + wx + 55, by + 100 + wobble)], fill=(255, 255, 255), width=5)
    # smile on bus
    draw.arc((bx + 200, by + 165 + wobble, bx + 340, by + 210 + wobble), 20, 160, fill=(50, 50, 50), width=4)
    for wx in (bx + 95, bx + 395):
        rot = int((frame * 14) % 360)
        draw.ellipse((wx, by + 200 + wobble, wx + 95, by + 295 + wobble), fill=(35, 35, 40))
        draw.ellipse((wx + 28, by + 228 + wobble, wx + 67, by + 267 + wobble), fill=(170, 170, 175))
        spoke_x = wx + 47 + int(18 * math.cos(math.radians(rot)))
        spoke_y = by + 247 + wobble + int(18 * math.sin(math.radians(rot)))
        draw.line([(wx + 47, by + 247 + wobble), (spoke_x, spoke_y)], fill=(110, 110, 115), width=6)


def draw_playground(draw: ImageDraw.ImageDraw, base_y: int, ctx: SceneContext) -> None:
    parallax = int(ctx.parallax * 0.2)
    draw.rounded_rectangle((680 - parallax, base_y - 210, 790 - parallax, base_y - 20), radius=18, fill=(255, 90, 90), outline=(200, 60, 60), width=4)
    draw.rounded_rectangle((830 - parallax, base_y - 280, 940 - parallax, base_y - 20), radius=18, fill=(80, 160, 255), outline=(50, 120, 200), width=4)
    draw.ellipse((760 - parallax, base_y - 300, 870 - parallax, base_y - 190), fill=(255, 210, 50), outline=(230, 170, 30), width=5)


def draw_bedroom_bg(draw: ImageDraw.ImageDraw, base_y: int, night: bool = False) -> None:
    wall = (45, 38, 85) if night else (255, 225, 245)
    bed = (100, 80, 180) if night else (170, 130, 250)
    draw.rectangle((0, 0, VIDEO_WIDTH, base_y + 20), fill=wall)
    draw.rounded_rectangle((90, base_y - 340, 520, base_y - 35), radius=32, fill=bed, outline=(80, 60, 140), width=5)
    draw.rectangle((90, base_y - 130, 520, base_y - 35), fill=(255, 255, 255))
    draw.ellipse((40, base_y - 280, 120, base_y - 200), fill=(255, 200, 220))
    draw.ellipse((620, base_y - 370, 780, base_y - 210), fill=(255, 240, 170))
    draw.rectangle((700, base_y - 210, 720, base_y - 100), fill=(180, 140, 90))


def draw_rainbow_road(draw: ImageDraw.ImageDraw, base_y: int, ctx: SceneContext) -> None:
    colors = ("#FF595E", "#FFCA3A", "#8AC926", "#1982C4", "#6A4C93", "#FF924C")
    shift = int(ctx.parallax * 0.15)
    for i, color in enumerate(colors):
        y = base_y - 50 - i * 20
        draw.rounded_rectangle((160 + shift, y, 920 + shift, y + 16), radius=10, fill=_hex(color))


def draw_color_blocks(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    blocks = ((255, 70, 70), (70, 130, 255), (255, 210, 50), (80, 195, 85), (200, 100, 255))
    labels = ("A", "B", "C", "1", "2")
    for i, color in enumerate(blocks):
        x = 110 + i * 185
        draw.rounded_rectangle((x, base_y - 380, x + 160, base_y - 130), radius=26, fill=color, outline=(255, 255, 255), width=6)
        draw.text((x + 48, base_y - 310), labels[i], font=load_font(68), fill=(255, 255, 255))


def draw_farm_barn(draw: ImageDraw.ImageDraw, base_y: int, ctx: SceneContext) -> None:
    px = int(ctx.parallax * 0.1)
    draw.polygon([(110 + px, base_y - 35), (110 + px, base_y - 290), (280 + px, base_y - 370), (450 + px, base_y - 290), (450 + px, base_y - 35)], fill=(185, 55, 55), outline=(140, 35, 35))
    draw.rectangle((175 + px, base_y - 190, 385 + px, base_y - 35), fill=(110, 65, 35))
    draw.polygon([(510 + px, base_y - 35), (510 + px, base_y - 230), (640 + px, base_y - 310), (770 + px, base_y - 230), (770 + px, base_y - 35)], fill=(215, 85, 65))


def draw_farm_animal(draw: ImageDraw.ImageDraw, cx: int, cy: int, kind: str, ctx: SceneContext) -> None:
    frame = ctx.frame_idx
    bounce = int(10 * math.sin(frame / 4 + cx * 0.01))
    cy += bounce
    draw_soft_shadow(draw, cx, cy + 88, 55, 14)
    if kind == "cow":
        glossy_ellipse(draw, (cx - 72, cy - 42, cx + 72, cy + 92), (65, 65, 75), (40, 40, 50))
        for spot in ((-30, 10), (20, -5), (40, 30)):
            draw.ellipse((cx + spot[0] - 15, cy + spot[1] - 12, cx + spot[0] + 15, cy + spot[1] + 12), fill=(240, 235, 230))
        draw.ellipse((cx - 58, cy - 72, cx - 18, cy - 12), fill=(65, 65, 75))
        draw.ellipse((cx + 18, cy - 72, cx + 58, cy - 12), fill=(65, 65, 75))
    elif kind == "duck":
        glossy_ellipse(draw, (cx - 58, cy - 12, cx + 58, cy + 72), (255, 215, 55), (215, 165, 25))
        draw.ellipse((cx - 38, cy - 48, cx + 38, cy + 2), fill=(255, 215, 55))
        draw.polygon([(cx + 32, cy - 12), (cx + 75, cy - 6), (cx + 32, cy + 6)], fill=(255, 130, 35))
    elif kind == "sheep":
        for dx, dy in ((-32, -22), (0, -38), (32, -22), (-16, 0), (16, 0), (0, 15)):
            draw.ellipse((cx + dx - 30, cy + dy - 30, cx + dx + 30, cy + dy + 30), fill=(248, 248, 252))
        draw.ellipse((cx - 24, cy - 12, cx + 24, cy + 32), fill=(35, 35, 45))
    else:
        glossy_ellipse(draw, (cx - 62, cy - 22, cx + 62, cy + 82), (255, 165, 185), (215, 115, 135))
        draw.ellipse((cx - 22, cy - 55, cx - 2, cy - 15), fill=(255, 165, 185))
        draw.ellipse((cx + 2, cy - 55, cx + 22, cy - 15), fill=(255, 165, 185))
        snout_wiggle = int(3 * math.sin(frame / 6))
        draw.ellipse((cx - 18 + snout_wiggle, cy - 8, cx + 18 + snout_wiggle, cy + 18), fill=(255, 200, 210))


def draw_picnic_scene(draw: ImageDraw.ImageDraw, base_y: int) -> None:
    draw.rounded_rectangle((200, base_y - 75, 880, base_y - 8), radius=22, fill=(255, 110, 130), outline=(200, 70, 90), width=4)
    for i, (x, color) in enumerate([(290, (170, 100, 60)), (440, (255, 200, 110)), (590, (255, 170, 190)), (740, (130, 200, 110))]):
        draw.ellipse((x, base_y - 125, x + 80, base_y - 35), fill=color)


def draw_butterflies(img: Image.Image, frame: int) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    colors = ((255, 150, 200), (150, 200, 255), (255, 220, 100))
    for i, color in enumerate(colors):
        t = frame / 30 + i * 2
        x = int(200 + i * 280 + 60 * math.sin(t))
        y = int(500 + 40 * math.cos(t * 1.3))
        wing = int(10 + 6 * math.sin(frame / 4 + i))
        c = (*color, 220)
        draw.ellipse((x - wing - 8, y - 6, x - 8, y + 6), fill=c)
        draw.ellipse((x + 8, y - 6, x + wing + 8, y + 6), fill=c)
        draw.ellipse((x - 3, y - 8, x + 3, y + 8), fill=(60, 40, 30, 255))
    img.paste(layer, (0, 0), layer)


def render_scene(draw: ImageDraw.ImageDraw, img: Image.Image, scene: str, base_y: int, ctx: SceneContext) -> None:
    theme = ctx.theme
    frame = ctx.frame_idx
    if scene == "bus":
        draw_yellow_bus(draw, base_y, ctx, theme.bus_color)
        draw_benny(draw, 740, base_y - 55, ctx)
        draw_bunny_friend(draw, 920, base_y - 25, ctx)
    elif scene == "rainbow_road":
        draw_rainbow_road(draw, base_y, ctx)
        draw_yellow_bus(draw, base_y, ctx, theme.bus_color)
        draw_bunny_friend(draw, 840, base_y - 35, ctx)
    elif scene == "song_circle":
        draw.ellipse((340, base_y - 230, 740, base_y + 25), fill=(255, 235, 110), outline=(255, 195, 50), width=6)
        draw.ellipse((370, base_y - 200, 710, base_y - 5), fill=(255, 245, 170))
        draw_benny(draw, 540, base_y - 85, ctx)
        draw_bunny_friend(draw, 720, base_y - 55, ctx)
    elif scene in {"bedroom_night", "moon_stars", "sleepy_meadow"}:
        draw_bedroom_bg(draw, base_y, night=True)
        draw_benny(draw, 540, base_y - 85, ctx)
        draw_bunny_friend(draw, 760, base_y - 45, ctx)
    elif scene in {"classroom", "color_blocks", "counting_garden"}:
        draw.rounded_rectangle((70, base_y - 440, 1010, base_y - 55), radius=32, fill=(255, 242, 215), outline=(210, 185, 140), width=7)
        draw_color_blocks(draw, base_y)
        draw_benny(draw, 510, base_y - 55, ctx)
    elif scene in {"picnic", "sharing_table", "friends_meadow"}:
        draw_picnic_scene(draw, base_y)
        draw_benny(draw, 510, base_y - 95, ctx)
        draw_bunny_friend(draw, 720, base_y - 65, ctx)
    elif scene in {"farm_barn", "animal_band", "meadow_animals"}:
        draw_farm_barn(draw, base_y, ctx)
        draw_farm_animal(draw, 250, base_y - 42, "cow", ctx)
        draw_farm_animal(draw, 470, base_y - 22, "duck", ctx)
        draw_farm_animal(draw, 690, base_y - 32, "sheep", ctx)
        draw_farm_animal(draw, 910, base_y - 12, "pig", ctx)
        draw_benny(draw, 560, base_y - 95, ctx)
    elif scene == "playground":
        draw_playground(draw, base_y, ctx)
        draw_benny(draw, 490, base_y - 55, ctx)
        draw_bunny_friend(draw, 670, base_y - 25, ctx)
    else:
        draw.ellipse((730, 170, 960, 400), fill=(255, 225, 90), outline=(255, 200, 50), width=5)
        draw_benny(draw, 510, base_y - 55, ctx)
        draw_bunny_friend(draw, 310, base_y - 35, ctx)

    if not theme.night_mode and scene not in {"bedroom_night", "moon_stars", "sleepy_meadow"}:
        draw_butterflies(img, frame)


def draw_caption_bar(img: Image.Image, line: str, line_progress: float, accent: tuple[int, int, int]) -> None:
    """Cocomelon-style bottom bar with word-by-word karaoke highlight."""
    words = line.split()
    if not words:
        return
    display_words = words[:10]
    if len(words) > 10:
        display_words[-1] = display_words[-1] + "..."

    bar_h = 200
    bar_y = VIDEO_HEIGHT - bar_h - 40
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # bar background with gradient feel
    dark = tuple(max(0, c - 40) for c in accent)
    draw.rounded_rectangle((30, bar_y, VIDEO_WIDTH - 30, bar_y + bar_h), radius=36, fill=(*accent, 240))
    draw.rounded_rectangle((40, bar_y + 6, VIDEO_WIDTH - 40, bar_y + bar_h - 6), radius=30, fill=(*dark, 200))

    font = load_font(46)
    word_idx = min(int(line_progress * len(display_words)), len(display_words) - 1)

    total_w = 0
    word_widths = []
    for w in display_words:
        bbox = draw.textbbox((0, 0), w, font=font)
        ww = bbox[2] - bbox[0]
        word_widths.append(ww)
        total_w += ww
    spacing = 18
    total_w += spacing * (len(display_words) - 1)
    x = (VIDEO_WIDTH - total_w) // 2
    y = bar_y + (bar_h - 50) // 2

    for i, word in enumerate(display_words):
        if i == word_idx:
            fill = (255, 255, 100)
            outline = (180, 120, 0)
        else:
            fill = (255, 255, 255)
            outline = (30, 30, 40)
        # stroke effect
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw.text((x + ox, y + oy), word, font=font, fill=outline)
        draw.text((x, y), word, font=font, fill=fill)
        x += word_widths[i] + spacing

    img.paste(layer, (0, 0), layer)


def draw_channel_badge(img: Image.Image, accent: tuple[int, int, int]) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((36, 36, 420, 110), radius=28, fill=(*accent, 230))
    draw.rounded_rectangle((44, 44, 412, 102), radius=24, fill=(255, 255, 255, 240))
    font = load_font(34)
    draw.text((62, 54), "Benny's Story World", font=font, fill=accent)
    img.paste(layer, (0, 0), layer)


def apply_vignette(img: Image.Image) -> None:
    layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2
    max_r = int(math.hypot(cx, cy))
    for r in range(max_r, 0, -12):
        alpha = int(18 * (r / max_r) ** 2)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, alpha))
    img.paste(layer, (0, 0), layer)


def apply_ken_burns(img: Image.Image, progress: float, zoom: float = 0.06) -> Image.Image:
    scale = 1.0 + zoom * progress
    w, h = img.size
    nw, nh = int(w * scale), int(h * scale)
    enlarged = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return enlarged.crop((left, top, left + w, top + h))


def render_cartoon_frame(
    line: str,
    line_idx: int,
    total_lines: int,
    frame_idx: int,
    frames_in_scene: int,
    theme: VideoTheme,
    *,
    global_frame: int = 0,
) -> Image.Image:
    line_progress = frame_idx / max(frames_in_scene - 1, 1)
    parallax = line_progress * 140 + global_frame * 2.5
    energetic = line_is_energetic(line)
    ctx = SceneContext(
        frame_idx=frame_idx,
        line_progress=line_progress,
        parallax=parallax,
        theme=theme,
        global_frame=global_frame,
        energetic=energetic,
    )

    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (255, 255, 255))
    scene = pick_scene(theme, line, line_idx)
    night = theme.night_mode or scene in {"bedroom_night", "moon_stars", "sleepy_meadow"}

    palette = SKY_PALETTES[theme.palette_idx % len(SKY_PALETTES)]
    draw_gradient_sky(img, palette, night=night)
    draw_clouds(img, frame_idx, parallax, night=night)

    if night:
        draw_moon_glow(img, frame_idx)
        draw_stars(img, frame_idx)
    else:
        draw_sun(img, frame_idx)
        draw_balloons(img, frame_idx, parallax)
        draw_birds(img, frame_idx, parallax)

    base_y = int(VIDEO_HEIGHT * 0.72)
    draw = ImageDraw.Draw(img)
    draw_foreground_flowers(draw, base_y, frame_idx, theme.accent)
    render_scene(draw, img, scene, base_y, ctx)

    if theme.category in {"nursery", "moral", "learning"}:
        draw_sparkles(img, frame_idx, count=14 if night else 22)

    if energetic and frame_idx % 8 < 4:
        img = draw_confetti(img, global_frame, density=12)

    draw_caption_bar(img, line, line_progress, theme.accent)
    draw_channel_badge(img, theme.accent)
    apply_vignette(img)

    # dynamic camera: zoom + pan direction changes per line
    pan_x = int(20 * math.sin(line_progress * math.pi))
    zoom = 0.08 + (0.04 if energetic else 0.0)
    img = apply_ken_burns(img, line_progress, zoom=zoom)
    if pan_x:
        canvas = Image.new("RGB", img.size, (135, 200, 235))
        canvas.paste(img, (pan_x, 0))
        img = canvas

    # beat pulse every ~15 frames
    if global_frame % 15 < 3:
        img = pulse_scale(img, 0.025 if energetic else 0.012)

    if line_idx == 0:
        img = hook_burst(img, frame_idx)

    if energetic:
        dx, dy = shake_offset(frame_idx, intensity=0.7)
        img = apply_shake(img, dx, dy)

    return img
