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
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import (
    ANALYTICS_DIR,
    KINOGO_VIDEO_HEIGHT,
    KINOGO_VIDEO_WIDTH,
    VIDEOS_DIR,
    ensure_dirs,
)
from scripts.ensure_music import ensure_music
from scripts.kinogo_seo import build_video_metadata
from scripts.movie_scene_detector import pick_highlight, probe_duration

# Render overlays at 1080p (fast), upscale final output to 4K Shorts.
WORK_W = 1080
WORK_H = 1920
FINAL_W = KINOGO_VIDEO_WIDTH
FINAL_H = KINOGO_VIDEO_HEIGHT

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


@dataclass
class SubtitleCue:
    start: float
    end: float
    text: str


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
        "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
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


def download_subtitles(url: str, dest_dir: Path) -> Path | None:
    cmd = [
        yt_dlp_bin(),
        "--write-auto-subs",
        "--sub-langs",
        "en",
        "--skip-download",
        "-o",
        str(dest_dir / "subs"),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    for path in sorted(dest_dir.glob("subs*.vtt")):
        return path
    return None


def download_music_audio(url: str, dest: Path) -> Path:
    cmd = [
        yt_dlp_bin(),
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "-o",
        str(dest.with_suffix(".%(ext)s")),
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    mp3 = dest.with_suffix(".mp3")
    if mp3.exists():
        return mp3
    raise RuntimeError(f"Music download failed: {url}")


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


def _draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    width: int = 3,
) -> None:
    x, y = xy
    for ox in range(-width, width + 1):
        for oy in range(-width, width + 1):
            if ox or oy:
                draw.text((x + ox, y + oy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:2]


def make_hook_overlay(hook: str, path: Path) -> None:
    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(64)
    text = hook.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (WORK_W - tw) // 2
    y = int(WORK_H * 0.08)
    pad = 36
    draw.rounded_rectangle(
        (x - pad, y - pad, x + tw + pad, y + th + pad),
        radius=32,
        fill=(0, 0, 0, 190),
    )
    _draw_outlined_text(draw, (x, y), text, font, (255, 255, 255, 255), (0, 0, 0, 255), width=4)
    img.save(path)


def make_music_bar_overlay(music: str, path: Path) -> None:
    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(30)
    label = f"🎵 Music Used: {music}"
    max_w = WORK_W - 80
    lines = _wrap_text(label, font, max_w) or [label[:60]]
    line_h = 38
    bar_h = line_h * len(lines) + 28
    bar_y = WORK_H - bar_h - 36
    draw.rounded_rectangle(
        (24, bar_y, WORK_W - 24, bar_y + bar_h),
        radius=18,
        fill=(0, 0, 0, 200),
    )
    y = bar_y + 14
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (WORK_W - tw) // 2
        _draw_outlined_text(draw, (x, y), line, font, (255, 255, 255, 255), (0, 0, 0, 255), width=2)
        y += line_h
    img.save(path)


def make_subtitle_overlay(text: str, path: Path) -> None:
    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(46)
    max_w = WORK_W - 100
    lines = _wrap_text(text, font, max_w)
    if not lines:
        img.save(path)
        return
    line_h = 54
    block_h = line_h * len(lines) + 28
    bar_y = int(WORK_H * 0.72) - block_h // 2
    draw.rounded_rectangle(
        (36, bar_y, WORK_W - 36, bar_y + block_h),
        radius=18,
        fill=(0, 0, 0, 160),
    )
    y = bar_y + 14
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (WORK_W - tw) // 2
        _draw_outlined_text(draw, (x, y), line, font, (255, 255, 255, 255), (0, 0, 0, 255), width=3)
        y += line_h
    img.save(path)


def _parse_vtt_timestamp(ts: str) -> float:
    h, m, rest = ts.strip().split(":")
    s, ms = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _clean_vtt_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_vtt(path: Path, clip_start: float, clip_end: float) -> list[SubtitleCue]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\n+", content)
    cues: list[SubtitleCue] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        timing_idx = 1 if lines[0].startswith("WEBVTT") or "-->" not in lines[0] else 0
        if timing_idx >= len(lines) or "-->" not in lines[timing_idx]:
            if "-->" in lines[0]:
                timing_idx = 0
            else:
                continue
        start_s, end_s = [p.strip().split()[0] for p in lines[timing_idx].split("-->")]
        start = _parse_vtt_timestamp(start_s)
        end = _parse_vtt_timestamp(end_s)
        if end <= clip_start or start >= clip_end:
            continue
        text = _clean_vtt_text(" ".join(lines[timing_idx + 1 :]))
        if not text or text in {".", ".."}:
            continue
        rel_start = max(0.0, start - clip_start)
        rel_end = min(clip_end - clip_start, end - clip_start)
        if rel_end - rel_start < 0.2:
            continue
        cues.append(SubtitleCue(rel_start, rel_end, text))
    cues.sort(key=lambda c: c.start)
    deduped: list[SubtitleCue] = []
    for cue in cues:
        if deduped and cue.text == deduped[-1].text and cue.start <= deduped[-1].end + 0.3:
            deduped[-1].end = max(deduped[-1].end, cue.end)
        else:
            deduped.append(cue)
    return deduped[:24]


def detect_crop(source: Path, start: float, duration: float) -> str | None:
    sample = min(20.0, duration)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-ss",
        str(start),
        "-t",
        str(sample),
        "-i",
        str(source),
        "-vf",
        "cropdetect=limit=20:round=2:reset=300",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    crops = re.findall(r"crop=(\d+:\d+:\d+:\d+)", proc.stderr)
    if not crops:
        return None
    return crops[-1]


def build_video_filter(crop_expr: str | None) -> str:
    parts: list[str] = []
    if crop_expr:
        parts.append(f"crop={crop_expr}")
    parts.extend(
        [
            f"scale={WORK_W}:{WORK_H}:force_original_aspect_ratio=increase:flags=lanczos",
            f"crop={WORK_W}:{WORK_H}",
            "setsar=1",
            "eq=contrast=1.18:saturation=1.22:brightness=0.01",
            "unsharp=7:7:1.2:7:7:0.0",
            "vignette=PI/4",
        ]
    )
    return ",".join(parts)


def _apply_overlays(base: Path, overlays: list[tuple[Path, str]], output: Path) -> None:
    """Burn all PNG overlays in a single ffmpeg pass."""
    inputs: list[str] = ["-i", str(base)]
    for png, _ in overlays:
        inputs.extend(["-i", str(png)])

    parts: list[str] = []
    prev = "[0:v]"
    for idx, (_, enable) in enumerate(overlays):
        src = f"[{idx + 1}:v]"
        tag = f"ov{idx}"
        out = f"[v{idx}]"
        parts.append(f"{src}format=rgba[{tag}]")
        parts.append(f"{prev}[{tag}]overlay=0:0:enable='{enable}'{out}")
        prev = out

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        *inputs,
        "-filter_complex",
        ";".join(parts),
        "-map",
        prev,
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "17",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(cmd, check=True)


def _upscale_to_4k(source: Path, output: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i",
        str(source),
        "-vf",
        f"scale={FINAL_W}:{FINAL_H}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "16",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(cmd, check=True)


def render_short(
    source: Path,
    output: Path,
    start: float,
    duration: float,
    hook: str | None = None,
    music_label: str | None = None,
    music_path: Path | None = None,
    subtitles: list[SubtitleCue] | None = None,
) -> None:
    hook_text = sanitize_hook(hook or "WATCH THIS")
    music_text = music_label or "Cinematic Ambient (Slowed & Reverb)"
    crop_expr = detect_crop(source, start, duration)
    vf = build_video_filter(crop_expr)

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
            "16",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-movflags",
            "+faststart",
            str(base),
        ]
        subprocess.run(cmd, check=True)

        current = base
        overlays: list[tuple[Path, str]] = []

        hook_png = tmp_path / "hook.png"
        make_hook_overlay(hook_text, hook_png)
        overlays.append((hook_png, "between(t,0,2.8)"))

        music_png = tmp_path / "music.png"
        make_music_bar_overlay(music_text, music_png)
        overlays.append((music_png, "gte(t,0)"))

        for i, cue in enumerate(subtitles or []):
            sub_png = tmp_path / f"sub_{i:03d}.png"
            make_subtitle_overlay(cue.text, sub_png)
            overlays.append((sub_png, f"between(t,{cue.start:.3f},{cue.end:.3f})"))

        if overlays:
            composed = tmp_path / "composed.mp4"
            _apply_overlays(current, overlays, composed)
            current = composed

        if music_path and music_path.exists():
            mixed = tmp_path / "mixed.mp4"
            mix_cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-i",
                str(current),
                "-i",
                str(music_path),
                "-filter_complex",
                (
                    "[0:a]volume=0.15[dialog];"
                    f"[1:a]aloop=loop=-1:size=2e+09,asetpts=N/SR/TB,atempo=0.88,atrim=0:{duration},"
                    "asetpts=PTS-STARTPTS,volume=0.85[music];"
                    "[dialog][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                ),
                "-map",
                "0:v",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-movflags",
                "+faststart",
                str(mixed),
            ]
            subprocess.run(mix_cmd, check=True)
            current = mixed

        final = tmp_path / "final.mp4"
        _upscale_to_4k(current, final)
        shutil.copy2(final, output)


def write_metadata(
    file_id: str,
    title: str,
    hook: str,
    source_url: str | None,
    music: str = "",
) -> Path:
    meta = build_video_metadata(title, music=music)
    meta.update(
        {
            "title": title,
            "privacyStatus": "public",
            "madeForKids": False,
            "source_url": source_url,
            "hook": hook,
            "music": music,
        }
    )
    path = VIDEOS_DIR / f"{file_id}-metadata.json"
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def resolve_music(music_label: str | None, music_url: str | None, tmp_path: Path) -> tuple[str, Path]:
    label = music_label or "Cinematic Ambient (Slowed & Reverb)"
    if music_url:
        return label, download_music_audio(music_url, tmp_path / "music")
    return label, ensure_music("cinematic")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cinematic movie Short from source clip")
    parser.add_argument("--source", help="Local video path")
    parser.add_argument("--url", help="YouTube or direct video URL")
    parser.add_argument("--id", help="Output id e.g. kinogo-2026-07-11-1")
    parser.add_argument("--hook", help="Opening hook text overlay")
    parser.add_argument("--title", help="Override YouTube title")
    parser.add_argument("--music", help="Music credit label shown at bottom")
    parser.add_argument("--music-url", help="Optional URL to download background music audio")
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
        music_label, music_path = resolve_music(args.music, args.music_url, tmp_path)

        subtitles: list[SubtitleCue] = []
        if source_url:
            vtt = download_subtitles(source_url, tmp_path)
            if vtt:
                clip_end = highlight.start + highlight.duration
                subtitles = parse_vtt(vtt, highlight.start, clip_end)

        render_short(
            src,
            output,
            highlight.start,
            highlight.duration,
            hook=hook,
            music_label=music_label,
            music_path=music_path,
            subtitles=subtitles,
        )
        meta_path = write_metadata(file_id, title, hook, source_url, music=music_label)

        report = {
            "file_id": file_id,
            "output": str(output),
            "metadata": str(meta_path),
            "source": str(src),
            "source_url": source_url,
            "title": title,
            "music": music_label,
            "subtitles": len(subtitles),
            "resolution": f"{FINAL_W}x{FINAL_H}",
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
