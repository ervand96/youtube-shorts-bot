"""Motion helpers: transitions, pulses, and lively overlays."""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from config.settings import VIDEO_HEIGHT, VIDEO_WIDTH

TRANSITION_FRAMES = 10


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def crossfade(img_a: Image.Image, img_b: Image.Image, t: float) -> Image.Image:
    t = ease_out_cubic(t)
    if img_a.mode != "RGB":
        img_a = img_a.convert("RGB")
    if img_b.mode != "RGB":
        img_b = img_b.convert("RGB")
    return Image.blend(img_a, img_b, t)


def slide_wipe(img_a: Image.Image, img_b: Image.Image, t: float) -> Image.Image:
    """Slide new scene in from the right with crossfade."""
    t = ease_out_cubic(t)
    w, h = img_a.size
    offset = int(w * t)
    canvas = Image.new("RGB", (w, h))
    canvas.paste(img_a, (-offset // 2, 0))
    canvas.paste(img_b, (w - offset, 0))
    return crossfade(canvas, img_b, t * 0.6)


def pulse_scale(img: Image.Image, amount: float) -> Image.Image:
    """Quick zoom punch for beat emphasis."""
    if amount <= 0:
        return img
    w, h = img.size
    scale = 1.0 + amount
    nw, nh = int(w * scale), int(h * scale)
    enlarged = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return enlarged.crop((left, top, left + w, top + h))


def shake_offset(frame: int, intensity: float = 1.0) -> tuple[int, int]:
    if intensity <= 0:
        return 0, 0
    return (
        int(6 * intensity * math.sin(frame * 1.7)),
        int(4 * intensity * math.cos(frame * 2.1)),
    )


def apply_shake(img: Image.Image, dx: int, dy: int) -> Image.Image:
    if dx == 0 and dy == 0:
        return img
    canvas = Image.new("RGB", img.size, (0, 0, 0))
    canvas.paste(img, (dx, dy))
    return canvas


def hook_burst(img: Image.Image, frame: int, total: int = 18) -> Image.Image:
    """Opening sparkle burst for the first line."""
    if frame >= total:
        return img
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    progress = frame / max(total - 1, 1)
    rng = random.Random(55)
    cx, cy = VIDEO_WIDTH // 2, int(VIDEO_HEIGHT * 0.38)
    for i in range(30):
        angle = rng.random() * math.tau
        dist = int(40 + progress * 320 + rng.randint(0, 80))
        x = cx + int(dist * math.cos(angle))
        y = cy + int(dist * math.sin(angle))
        size = max(2, int(8 * (1 - progress)))
        colors = ((255, 230, 80), (255, 120, 180), (120, 200, 255), (255, 255, 255))
        c = colors[i % len(colors)]
        alpha = int(220 * (1 - progress * 0.7))
        draw.ellipse((x - size, y - size, x + size, y + size), fill=(*c, alpha))
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")


def draw_confetti(img: Image.Image, frame: int, density: int = 16) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rng = random.Random(99)
    colors = ((255, 90, 90), (255, 200, 60), (80, 180, 255), (120, 220, 100), (220, 120, 255))
    for i in range(density):
        x = (rng.randint(0, VIDEO_WIDTH) + frame * (3 + i % 5)) % VIDEO_WIDTH
        y = (rng.randint(0, VIDEO_HEIGHT) + frame * (5 + i % 7)) % VIDEO_HEIGHT
        w, h = 8 + i % 6, 14 + i % 8
        rot = (frame * 6 + i * 40) % 360
        # simple falling rectangles
        draw.rectangle((x, y, x + w, y + h), fill=(*colors[i % len(colors)], 200))
    out = img.convert("RGBA")
    out.alpha_composite(layer)
    return out.convert("RGB")
