#!/usr/bin/env python3
"""Build professional 3D-style kids cartoon Short using AI scene generation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ASSETS_DIR, VIDEOS_DIR, ensure_dirs, get_env
from scripts.ai_media import generate_scene_image, image_to_video_clip
from scripts.build_video_basic import get_audio_duration
from scripts.scene_planner import build_scene_prompts


def concat_scene_clips(clips: list[Path], output_path: Path) -> None:
    list_file = output_path.with_suffix(".txt")
    list_file.write_text("".join(f"file '{c}'\n" for c in clips))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    list_file.unlink(missing_ok=True)


def add_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    music = ASSETS_DIR / "background.mp3"
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path)]
    if music.exists():
        cmd += [
            "-i",
            str(music),
            "-filter_complex",
            "[1:a]volume=1.0[voice];[2:a]volume=0.08[music];[voice][music]amix=inputs=2:duration=first[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
        ]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)


def build_premium_video(script_path: Path, audio_path: Path, output_path: Path, date_str: str) -> None:
    duration = get_audio_duration(audio_path)
    scenes = build_scene_prompts(script_path, max_scenes=5)
    scene_seconds = max(duration / len(scenes), 3.0)

    work_dir = VIDEOS_DIR / f"{date_str}-scenes"
    work_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []

    for scene in scenes:
        idx = scene["index"]
        print(f"Scene {idx + 1}/{len(scenes)}: generating 3D image...")
        image_path = work_dir / f"scene_{idx:02d}.png"
        clip_path = work_dir / f"scene_{idx:02d}.mp4"
        generate_scene_image(scene["prompt"], image_path)
        print(f"Scene {idx + 1}: animating...")
        image_to_video_clip(image_path, clip_path, scene_seconds)
        clips.append(clip_path)

    silent_path = work_dir / "silent_concat.mp4"
    concat_scene_clips(clips, silent_path)
    add_audio(silent_path, audio_path, output_path)
    print(f"Premium 3D cartoon video: {output_path} ({duration:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build premium 3D kids cartoon Short")
    parser.add_argument("--date", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--audio")
    args = parser.parse_args()

    ensure_dirs()
    if not get_env("REPLICATE_API_TOKEN"):
        raise SystemExit("Set REPLICATE_API_TOKEN for premium 3D videos. Get one at replicate.com/account/api-tokens")

    script_path = Path(args.script)
    audio_path = Path(args.audio) if args.audio else ROOT / "audio" / f"{args.date}.mp3"
    output_path = VIDEOS_DIR / f"{args.date}.mp4"
    build_premium_video(script_path, audio_path, output_path, args.date)


if __name__ == "__main__":
    main()
