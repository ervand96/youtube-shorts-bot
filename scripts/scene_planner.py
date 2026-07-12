"""Plan visual scenes and AI cartoon prompts from a kids script."""

from __future__ import annotations

import re
from pathlib import Path

STYLE_PREFIX = (
    "Professional 3D kids cartoon still frame, NuNu TV / Cocomelon style, "
    "cute toddler boy Benny with blonde hair tuft, big sparkling eyes, blue overalls, "
    "soft studio lighting, vibrant saturated colors, cheerful wholesome mood, "
    "vertical 9:16 composition, no text, no watermark, no letters. "
)

SCENE_TEMPLATES = [
    "Hook scene: {line} Benny jumping with excitement, bright sunbeams, magical sparkles.",
    "Scene: {line} Benny with cute white bunny friend in colorful meadow, flowers, blue sky.",
    "Scene: {line} Close-up of Benny singing happily, expressive face, pastel background.",
    "Scene: {line} Benny meeting animal friends, celebration, rainbow in the sky.",
    "Happy ending: {line} Benny waving bye-bye, soft clouds and stars, warm glow.",
]


def extract_script_lines(script_path: Path) -> list[str]:
    content = script_path.read_text(encoding="utf-8")
    match = re.search(r"##\s*Script\s*\n+([\s\S]+?)(?:\n##|\Z)", content, re.IGNORECASE)
    text = match.group(1).strip() if match else content
    lines = [ln.strip() for ln in text.split("\n") if ln.strip() and not ln.startswith("#")]
    return lines or [text[:120]]


def group_lines(lines: list[str], max_scenes: int = 5) -> list[str]:
    if len(lines) <= max_scenes:
        return lines
    groups: list[str] = []
    chunk = max(1, len(lines) // max_scenes)
    for i in range(0, len(lines), chunk):
        groups.append(" ".join(lines[i : i + chunk]))
    return groups[:max_scenes]


def build_scene_prompts(script_path: Path, max_scenes: int = 5) -> list[dict]:
    lines = group_lines(extract_script_lines(script_path), max_scenes=max_scenes)
    scenes = []
    for idx, line in enumerate(lines):
        template = SCENE_TEMPLATES[min(idx, len(SCENE_TEMPLATES) - 1)]
        prompt = STYLE_PREFIX + template.format(line=line)
        scenes.append({"index": idx, "caption": line, "prompt": prompt})
    return scenes
