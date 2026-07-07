"""Basic 2D cartoon video builder (fallback without Replicate)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from config.settings import ASSETS_DIR, VIDEO_FPS
from scripts.cartoon_renderer import build_video_theme, extract_script_lines, render_cartoon_frame


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
    theme = build_video_theme(script_path)
    duration = get_audio_duration(audio_path)
    seconds_per_line = max(duration / len(lines), 2.0)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        frame_idx = 0
        for line_idx, line in enumerate(lines):
            frames_for_line = max(int(seconds_per_line * VIDEO_FPS), VIDEO_FPS * 2)
            for f in range(frames_for_line):
                frame = render_cartoon_frame(line, line_idx, len(lines), f, frames_for_line, theme)
                frame.save(tmp_path / f"frame_{frame_idx:05d}.png")
                frame_idx += 1

        music = ASSETS_DIR / "background.mp3"
        cmd = ["ffmpeg", "-y", "-framerate", str(VIDEO_FPS), "-i", str(tmp_path / "frame_%05d.png"), "-i", str(audio_path)]
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

    print(f"Built 2D cartoon: {output_path} ({duration:.1f}s, {frame_idx} frames)")
