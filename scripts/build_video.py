#!/usr/bin/env python3
"""Build animated kids cartoon Short with characters, scenes, and voiceover."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ASSETS_DIR, VIDEO_FPS, VIDEOS_DIR, ensure_dirs
from scripts.cartoon_renderer import extract_script_lines, render_cartoon_frame


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


def build_video(script_path: Path, audio_path: Path, output_path: Path) -> None:
    lines = extract_script_lines(script_path)
    duration = get_audio_duration(audio_path)
    seconds_per_line = max(duration / len(lines), 2.0)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        frame_idx = 0
        for line_idx, line in enumerate(lines):
            frames_for_line = max(int(seconds_per_line * VIDEO_FPS), VIDEO_FPS * 2)
            for f in range(frames_for_line):
                frame = render_cartoon_frame(line, line_idx, len(lines), f, frames_for_line)
                frame.save(tmp_path / f"frame_{frame_idx:05d}.png")
                frame_idx += 1

        music = ASSETS_DIR / "background.mp3"
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(VIDEO_FPS),
            "-i",
            str(tmp_path / "frame_%05d.png"),
            "-i",
            str(audio_path),
        ]
        if music.exists():
            cmd += [
                "-i",
                str(music),
                "-filter_complex",
                "[1:a]volume=1.0[a1];[2:a]volume=0.10[a2];[a1][a2]amix=inputs=2:duration=first[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
            ]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]

        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    print(f"Built animated cartoon: {output_path} ({duration:.1f}s, {frame_idx} frames)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build animated kids cartoon Short")
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
