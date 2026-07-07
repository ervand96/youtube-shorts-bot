#!/usr/bin/env python3
"""Build 9:16 vertical Short video with subtitles and voiceover."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ASSETS_DIR, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH, VIDEOS_DIR, ensure_dirs


PALETTES = [
    ("#FF6B9D", "#FFC371"),
    ("#4FACFE", "#00F2FE"),
    ("#A18CD1", "#FBC2EB"),
    ("#F6D365", "#FDA085"),
    ("#84FAB0", "#8FD3F4"),
]


def extract_script_lines(script_path: Path) -> list[str]:
    content = script_path.read_text(encoding="utf-8")
    match = re.search(r"##\s*Script\s*\n+([\s\S]+?)(?:\n##|\Z)", content, re.IGNORECASE)
    text = match.group(1).strip() if match else content
    lines = []
    for raw in text.split("\n"):
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines or [text[:120]]


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def gradient_background(size: tuple[int, int], colors: tuple[str, str]) -> Image.Image:
    width, height = size
    top = tuple(int(colors[0].lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    bottom = tuple(int(colors[1].lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return img


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines[:4]


def render_frame(text: str, palette_idx: int, frame_idx: int) -> Image.Image:
    colors = PALETTES[palette_idx % len(PALETTES)]
    img = gradient_background((VIDEO_WIDTH, VIDEO_HEIGHT), colors)
    draw = ImageDraw.Draw(img)

    # Decorative circles for cartoon feel
    for i, (cx, cy, r) in enumerate([(180, 260, 90), (900, 420, 120), (540, 1500, 160)]):
        offset = int(8 * math.sin((frame_idx + i * 10) / 12))
        draw.ellipse(
            (cx - r + offset, cy - r, cx + r + offset, cy + r),
            fill=(255, 255, 255),
            outline=(255, 255, 255),
        )

    font = load_font(72)
    wrapped = wrap_text(draw, text, font, VIDEO_WIDTH - 160)
    total_height = sum(draw.textbbox((0, 0), line, font=font)[3] for line in wrapped) + 20 * len(wrapped)
    y = (VIDEO_HEIGHT - total_height) // 2
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (VIDEO_WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x + 3, y + 3), line, font=font, fill="#000000")
        draw.text((x, y), line, font=font, fill="#FFFFFF")
        y += bbox[3] - bbox[1] + 20

    return img


def build_video(script_path: Path, audio_path: Path, output_path: Path) -> None:
    lines = extract_script_lines(script_path)
    duration = get_audio_duration(audio_path)
    seconds_per_line = max(duration / len(lines), 1.5)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        frame_paths: list[Path] = []
        frame_idx = 0
        for line_idx, line in enumerate(lines):
            frames_for_line = max(int(seconds_per_line * VIDEO_FPS), VIDEO_FPS)
            for _ in range(frames_for_line):
                frame = render_frame(line, line_idx, frame_idx)
                frame_path = tmp_path / f"frame_{frame_idx:05d}.png"
                frame.save(frame_path)
                frame_paths.append(frame_path)
                frame_idx += 1

        concat_file = tmp_path / "frames.txt"
        concat_file.write_text("".join(f"file '{p}'\n" for p in frame_paths))

        silent_video = tmp_path / "silent.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-vf",
                f"fps={VIDEO_FPS},scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(silent_video),
            ],
            check=True,
            capture_output=True,
        )

        music = ASSETS_DIR / "background.mp3"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(audio_path),
        ]
        if music.exists():
            cmd += ["-i", str(music), "-filter_complex", "[1:a]volume=1.0[a1];[2:a]volume=0.12[a2];[a1][a2]amix=inputs=2:duration=first[aout]", "-map", "0:v", "-map", "[aout]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]

        cmd += [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    print(f"Built video: {output_path} ({duration:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build vertical Short MP4")
    parser.add_argument("--date", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--audio", help="Audio path override")
    args = parser.parse_args()

    ensure_dirs()
    script_path = Path(args.script)
    audio_path = Path(args.audio) if args.audio else ROOT / "audio" / f"{args.date}.mp3"
    output_path = VIDEOS_DIR / f"{args.date}.mp4"

    if not script_path.exists():
        raise FileNotFoundError(script_path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    build_video(script_path, audio_path, output_path)


if __name__ == "__main__":
    main()
