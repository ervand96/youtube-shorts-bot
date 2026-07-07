#!/usr/bin/env python3
"""Build animated kids cartoon Short — premium 3D if Replicate token is set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import VIDEOS_DIR, ensure_dirs, get_env


def main() -> None:
    parser = argparse.ArgumentParser(description="Build kids cartoon Short video")
    parser.add_argument("--date", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--audio", help="Audio path override")
    parser.add_argument("--premium", action="store_true", help="Force 3D AI pipeline")
    parser.add_argument("--basic", action="store_true", help="Force basic 2D cartoon pipeline")
    args = parser.parse_args()

    ensure_dirs()
    script_path = Path(args.script)
    audio_path = Path(args.audio) if args.audio else ROOT / "audio" / f"{args.date}.mp3"
    output_path = VIDEOS_DIR / f"{args.date}.mp4"

    if not script_path.exists():
        raise FileNotFoundError(script_path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    use_premium = args.premium or (get_env("REPLICATE_API_TOKEN") and not args.basic)

    if use_premium:
        from scripts.build_video_premium import build_premium_video

        build_premium_video(script_path, audio_path, output_path, args.date)
    else:
        from scripts.build_video_basic import build_video

        build_video(script_path, audio_path, output_path)


if __name__ == "__main__":
    main()
