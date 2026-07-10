#!/usr/bin/env python3
"""Render a vertical movie Short with cinematic effects from a source clip."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ANALYTICS_DIR, VIDEOS_DIR, VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH, ensure_dirs
from scripts.kinogo_seo import build_video_metadata
from scripts.movie_scene_detector import pick_highlight, probe_duration

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def yt_dlp_bin() -> str:
    venv = ROOT / ".venv" / "bin" / "yt-dlp"
    if venv.exists():
        return str(venv)
    found = shutil.which("yt-dlp")
    if found:
        return found
    raise RuntimeError("yt-dlp not found. Run: .venv/bin/pip install yt-dlp")


def download_source(url: str, dest: Path) -> dict:
    cmd = [
        yt_dlp_bin(),
        "-f",
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format",
        "mp4",
        "--print",
        "%(title)s",
        "--print",
        "after_move:%(filepath)s",
        "-o",
        str(dest.parent / "src.%(ext)s"),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    title = lines[0] if lines else "Movie Short"
    filepath = lines[-1].replace("after_move:", "").strip()
    return {"title": title, "path": Path(filepath)}


def sanitize_hook(text: str, max_len: int = 42) -> str:
    hook = re.sub(r"\s+", " ", text).strip(" \"'|#")
    if len(hook) > max_len:
        hook = hook[: max_len - 1].rstrip() + "…"
    return hook or "Movie moment"


def build_title(source_title: str, hook: str | None = None) -> str:
    h = sanitize_hook(hook or source_title)
    base = f'"{h}" | Movie Edit 🔥 #Shorts'
    if len(base) <= 100:
        return base
    return f"{h[:60]} | Movie Edit #Shorts"


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_hook_overlay(hook: str, path: Path) -> None:
    """Transparent PNG banner for ffmpeg overlay (no drawtext filter needed)."""
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(64)
    text = hook.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (VIDEO_WIDTH - tw) // 2
    y = int(VIDEO_HEIGHT * 0.10)
    pad = 18
    draw.rounded_rectangle(
        (x - pad, y - pad, x + tw + pad, y + th + pad),
        radius=16,
        fill=(0, 0, 0, 170),
    )
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 220))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    img.save(path)


def render_short(
    source: Path,
    output: Path,
    start: float,
    duration: float,
    hook: str | None = None,
) -> None:
    """Crop 9:16, punch contrast, subtle zoom pulse, vignette, opening hook overlay."""
    hook_text = sanitize_hook(hook or "WATCH THIS")

    vf = (
        f"crop=ih*9/16:ih:(iw-ow)/2:0,"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:flags=lanczos,"
        f"eq=contrast=1.10:saturation=1.15:brightness=0.02,"
        f"unsharp=5:5:0.8:5:5:0.0,"
        f"vignette=PI/5"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        base = tmp_path / "base.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-i",
            str(source),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(base),
        ]
        subprocess.run(cmd, check=True)

        overlay_png = tmp_path / "hook.png"
        make_hook_overlay(hook_text, overlay_png)
        overlay_cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-i",
            str(base),
            "-i",
            str(overlay_png),
            "-filter_complex",
            "[1]format=rgba[hook];[0][hook]overlay=0:0:enable='between(t,0,2.5)'",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]
        subprocess.run(overlay_cmd, check=True)


def write_metadata(file_id: str, title: str, hook: str, source_url: str | None) -> Path:
    meta = build_video_metadata(title)
    meta.update(
        {
            "title": title,
            "privacyStatus": "public",
            "madeForKids": False,
            "source_url": source_url,
            "hook": hook,
        }
    )
    path = VIDEOS_DIR / f"{file_id}-metadata.json"
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cinematic movie Short from source clip")
    parser.add_argument("--source", help="Local video path")
    parser.add_argument("--url", help="YouTube or direct video URL")
    parser.add_argument("--id", help="Output id e.g. kinogo-2026-07-11-1")
    parser.add_argument("--hook", help="Opening hook text overlay")
    parser.add_argument("--title", help="Override YouTube title")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    if not args.source and not args.url:
        raise SystemExit("Provide --source or --url")

    ensure_dirs()
    file_id = args.id or f"kinogo-{date.today().isoformat()}-1"
    output = VIDEOS_DIR / f"{file_id}.mp4"
    log_dir = ANALYTICS_DIR / "kinogo"
    log_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_url = args.url
        if args.source:
            src = Path(args.source)
            source_title = args.title or src.stem
        else:
            info = download_source(args.url, tmp_path / "src.mp4")
            src = info["path"]
            source_title = args.title or info["title"]

        highlight = pick_highlight(src)
        hook = args.hook or sanitize_hook(source_title)
        title = build_title(source_title, hook)

        render_short(src, output, highlight.start, highlight.duration, hook=hook)
        meta_path = write_metadata(file_id, title, hook, source_url)

        report = {
            "file_id": file_id,
            "output": str(output),
            "metadata": str(meta_path),
            "source": str(src),
            "source_url": source_url,
            "title": title,
            "highlight": {
                "start": highlight.start,
                "duration": highlight.duration,
                "score": highlight.score,
                "scene_cuts": highlight.scene_cuts,
                "peak_db": highlight.peak_db,
            },
            "source_duration": probe_duration(src),
        }
        log_path = log_dir / f"{file_id}-build.json"
        log_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
