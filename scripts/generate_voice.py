#!/usr/bin/env python3
"""Generate voiceover from a script markdown file."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import AUDIO_DIR, ensure_dirs, get_env


def extract_script_text(script_path: Path) -> str:
    content = script_path.read_text(encoding="utf-8")
    match = re.search(r"##\s*Script\s*\n+([\s\S]+?)(?:\n##|\Z)", content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.startswith("#")]
    return " ".join(paragraphs[-3:])


async def generate_edge_tts(text: str, output_path: Path, voice: str = "en-US-AnaNeural") -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def generate_elevenlabs(text: str, output_path: Path) -> None:
    api_key = get_env("ELEVENLABS_API_KEY")
    voice_id = get_env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    response.raise_for_status()
    output_path.write_bytes(response.content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate voiceover MP3")
    parser.add_argument("--date", required=True, help="Date string YYYY-MM-DD")
    parser.add_argument("--script", required=True, help="Path to script markdown")
    parser.add_argument("--voice", default="en-US-AnaNeural", help="edge-tts voice name")
    args = parser.parse_args()

    ensure_dirs()
    script_path = Path(args.script)
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    text = extract_script_text(script_path)
    if not text:
        raise ValueError("Could not extract script text")

    output_path = AUDIO_DIR / f"{args.date}.mp3"
    print(f"Generating voiceover ({len(text)} chars) -> {output_path}")

    if get_env("ELEVENLABS_API_KEY"):
        generate_elevenlabs(text, output_path)
    else:
        asyncio.run(generate_edge_tts(text, output_path, args.voice))

    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
