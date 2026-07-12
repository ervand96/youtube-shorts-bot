"""Generate kids cartoon scene images via Google Gemini (Nano Banana family)."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

from config.settings import get_env

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _api_key() -> str:
    key = get_env("GEMINI_API_KEY") or get_env("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is required for VIDEO_MODE=gemini. "
            "Create one at https://aistudio.google.com/apikey"
        )
    return key


def _model() -> str:
    return get_env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")


def generate_gemini_image(prompt: str, output_path: Path, retries: int = 3) -> Path:
    """Text → PNG via Gemini native image generation. Vertical 9:16 kids cartoon."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = _model()
    url = f"{GEMINI_BASE}/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": _api_key()}
    full_prompt = (
        f"{prompt}\n\n"
        "CRITICAL: vertical 9:16 portrait frame, 1080x1920 composition, "
        "NO text, NO letters, NO watermark, NO logos, NO UI."
    )
    body = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=180)
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"Gemini rate limit — wait {wait}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            image_bytes = _extract_image_bytes(data)
            output_path.write_bytes(image_bytes)
            return output_path
        except Exception as exc:
            last_err = exc
            print(f"Gemini image attempt {attempt + 1} failed: {exc}")
            time.sleep(3 * (attempt + 1))

    raise RuntimeError(f"Gemini image generation failed after {retries} tries: {last_err}")


def _extract_image_bytes(data: dict) -> bytes:
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"No candidates in Gemini response: {json.dumps(data)[:400]}")
    parts = candidates[0].get("content", {}).get("parts") or []
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if not inline:
            continue
        mime = (inline.get("mimeType") or inline.get("mime_type") or "").lower()
        b64 = inline.get("data")
        if b64 and ("image" in mime or not mime):
            return base64.b64decode(b64)
    raise RuntimeError(f"No image part in Gemini response: {json.dumps(data)[:500]}")
