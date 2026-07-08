"""Basic 2D cartoon video builder (fallback without Replicate)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from config.settings import ASSETS_DIR, VIDEO_FPS
from scripts.cartoon_renderer import build_video_theme, extract_script_lines, parse_script_category, render_cartoon_frame
from scripts.ensure_music import ensure_music
from scripts.motion_effects import TRANSITION_FRAMES, slide_wipe


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
        prev_tail: list[Image.Image] = []

        for line_idx, line in enumerate(lines):
            frames_for_line = max(int(seconds_per_line * VIDEO_FPS), VIDEO_FPS * 2)
            line_frames: list[Image.Image] = []

            for f in range(frames_for_line):
                frame = render_cartoon_frame(
                    line,
                    line_idx,
                    len(lines),
                    f,
                    frames_for_line,
                    theme,
                    global_frame=frame_idx,
                )
                line_frames.append(frame)

            # Crossfade transition from previous line
            if prev_tail and line_frames:
                overlap = min(TRANSITION_FRAMES, len(prev_tail), len(line_frames))
                for t in range(overlap):
                    blend_t = t / max(overlap - 1, 1)
                    blended = slide_wipe(prev_tail[-(overlap - t)], line_frames[t], blend_t)
                    blended.save(tmp_path / f"frame_{frame_idx:05d}.png")
                    frame_idx += 1
                for frame in line_frames[overlap:]:
                    frame.save(tmp_path / f"frame_{frame_idx:05d}.png")
                    frame_idx += 1
            else:
                for frame in line_frames:
                    frame.save(tmp_path / f"frame_{frame_idx:05d}.png")
                    frame_idx += 1

            prev_tail = line_frames[-TRANSITION_FRAMES:]

        category = parse_script_category(script_path)
        music = ensure_music(category)
        fallback = ASSETS_DIR / "background.mp3"
        if not music.exists() and fallback.exists():
            music = fallback
        cmd = ["ffmpeg", "-y", "-framerate", str(VIDEO_FPS), "-i", str(tmp_path / "frame_%05d.png"), "-i", str(audio_path)]
        if music.exists():
            cmd += [
                "-i",
                str(music),
                "-filter_complex",
                "[1:a]volume=1.0[a1];[2:a]volume=0.28,aloop=loop=-1:size=2e+09[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=0[aout]",
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
            "21",
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
