#!/usr/bin/env python3
"""Build animated kids cartoon Short — Gemini / Replicate premium / free 2D."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import VIDEOS_DIR, ensure_dirs, use_gemini_video, use_premium_video


def main() -> None:
    parser = argparse.ArgumentParser(description="Build kids cartoon Short video")
    parser.add_argument("--id", help="File id e.g. 2026-07-09-1")
    parser.add_argument("--date", help="Legacy date id YYYY-MM-DD")
    parser.add_argument("--script", required=True)
    parser.add_argument("--audio", help="Audio path override")
    parser.add_argument("--premium", action="store_true")
    parser.add_argument("--gemini", action="store_true")
    parser.add_argument("--basic", action="store_true")
    args = parser.parse_args()
    file_id = args.id or args.date
    if not file_id:
        raise SystemExit("Provide --id or --date")

    ensure_dirs()
    script_path = Path(args.script)
    audio_path = Path(args.audio) if args.audio else ROOT / "audio" / f"{file_id}.mp3"
    output_path = VIDEOS_DIR / f"{file_id}.mp4"

    if not script_path.exists():
        raise FileNotFoundError(script_path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    if args.basic:
        from scripts.build_video_basic import build_video

        build_video(script_path, audio_path, output_path)
        return

    if args.gemini or use_gemini_video():
        from scripts.build_video_gemini import build_gemini_video

        build_gemini_video(script_path, audio_path, output_path, file_id)
        return

    if args.premium or use_premium_video():
        from scripts.build_video_premium import build_premium_video

        build_premium_video(script_path, audio_path, output_path, file_id)
        return

    from scripts.build_video_basic import build_video

    build_video(script_path, audio_path, output_path)


if __name__ == "__main__":
    main()
