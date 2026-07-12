#!/usr/bin/env python3
"""Build kids Short with Gemini Nano Banana images + Ken Burns motion (automatable)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import VIDEOS_DIR, get_env
from scripts.ai_media import _ken_burns_clip
from scripts.build_video_basic import get_audio_duration
from scripts.build_video_premium import add_audio, concat_scene_clips
from scripts.ensure_music import ensure_music
from scripts.gemini_media import generate_gemini_image
from scripts.scene_planner import build_scene_prompts


def build_gemini_video(script_path: Path, audio_path: Path, output_path: Path, file_id: str) -> None:
    if not (get_env("GEMINI_API_KEY") or get_env("GOOGLE_API_KEY")):
        raise RuntimeError("Set GEMINI_API_KEY for VIDEO_MODE=gemini")

    duration = get_audio_duration(audio_path)
    # Keep scene count low for free/cheap quotas (1 Short/day)
    max_scenes = int(get_env("GEMINI_MAX_SCENES", "4") or "4")
    scenes = build_scene_prompts(script_path, max_scenes=max_scenes)
    scene_seconds = max(duration / len(scenes), 3.0)

    work_dir = VIDEOS_DIR / f"{file_id}-gemini-scenes"
    work_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []

    for scene in scenes:
        idx = scene["index"]
        print(f"Gemini scene {idx + 1}/{len(scenes)}: {scene['caption'][:60]}...")
        image_path = work_dir / f"scene_{idx:02d}.png"
        clip_path = work_dir / f"scene_{idx:02d}.mp4"
        generate_gemini_image(scene["prompt"], image_path)
        print(f"  animating Ken Burns ({scene_seconds:.1f}s)...")
        _ken_burns_clip(image_path, clip_path, scene_seconds)
        clips.append(clip_path)

    silent_path = work_dir / "silent_concat.mp4"
    concat_scene_clips(clips, silent_path)

    try:
        from scripts.cartoon_renderer import parse_script_category

        category = parse_script_category(script_path)
        ensure_music(category)
    except Exception:
        pass

    add_audio(silent_path, audio_path, output_path)
    print(f"Gemini cartoon video: {output_path} ({duration:.1f}s, {len(scenes)} scenes)")
