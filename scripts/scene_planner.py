"""Plan visual scenes and 3D-style prompts from a kids script."""

from __future__ import annotations

import re
from pathlib import Path

STYLE_PREFIX = (
    "Professional 3D kids cartoon animation frame, NuNu TV Cocomelon style, "
    "cute toddler characters with big eyes, vibrant saturated colors, soft lighting, "
    "high quality 3D render, cheerful mood, vertical 9:16 composition, no text, no watermark. "
)

SCENE_TEMPLATES = [
    "Scene: {line} Toddler and cute bunny in colorful meadow with flowers and blue sky.",
    "Scene: {line} Friendly 3D bunny character close-up, expressive face, pastel background.",
    "Scene: {line} Bunny hopping near wooden garden gate, magical sparkles, kids storybook style.",
    "Scene: {line} Sunny garden with rainbow, bunny meeting animal friends, celebration.",
    "Scene: {line} Happy ending, bunny smiling with book, stars and soft clouds.",
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
