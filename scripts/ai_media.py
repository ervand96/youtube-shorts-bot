"""Generate 3D-style scene images and clips via Replicate."""

from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path

from config.settings import get_env

REPLICATE_API = "https://api.replicate.com/v1/predictions"


def _headers() -> dict[str, str]:
    token = get_env("REPLICATE_API_TOKEN")
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN is required for premium 3D videos")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }


def _post_prediction(model: str, input_data: dict) -> dict:
    import json

    import requests

    payload = {"input": input_data}
    if ":" in model:
        payload["version"] = model.split(":", 1)[1]
        url = REPLICATE_API
        payload = {"version": model.split(":", 1)[1], "input": input_data}
    else:
        url = f"{REPLICATE_API.replace('/predictions', '')}/models/{model}/predictions"

    resp = requests.post(url, headers=_headers(), json={"input": input_data}, timeout=600)
    resp.raise_for_status()
    data = resp.json()

    status = data.get("status")
    get_url = data["urls"]["get"]
    while status not in {"succeeded", "failed", "canceled"}:
        time.sleep(2)
        poll = requests.get(get_url, headers=_headers(), timeout=120)
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")

    if status != "succeeded":
        raise RuntimeError(f"Replicate prediction failed: {data.get('error')}")
    return data


def download_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def generate_scene_image(prompt: str, output_path: Path) -> Path:
    import requests

    token = get_env("REPLICATE_API_TOKEN")
    model = get_env("REPLICATE_IMAGE_MODEL", "black-forest-labs/flux-schnell")
    url = f"https://api.replicate.com/v1/models/{model}/predictions"
    resp = requests.post(
        url,
        headers=_headers(),
        json={
            "input": {
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "output_format": "png",
                "num_outputs": 1,
            }
        },
        timeout=600,
    )
    resp.raise_for_status()
    data = resp.json()
    get_url = data["urls"]["get"]
    while data.get("status") not in {"succeeded", "failed", "canceled"}:
        time.sleep(2)
        poll = requests.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
        poll.raise_for_status()
        data = poll.json()

    if data.get("status") != "succeeded":
        raise RuntimeError(f"Image generation failed: {data.get('error')}")

    out = data["output"]
    image_url = out[0] if isinstance(out, list) else out
    return download_file(image_url, output_path)


def image_to_video_clip(image_path: Path, output_path: Path, seconds: float) -> Path:
    """Try AI motion clip; fallback to cinematic Ken Burns on the AI image."""
    token = get_env("REPLICATE_API_TOKEN")
    use_svd = get_env("REPLICATE_USE_SVD", "1") == "1"
    if use_svd:
        try:
            import base64
            import requests

            image_b64 = base64.b64encode(image_path.read_bytes()).decode()
            data_uri = f"data:image/png;base64,{image_b64}"
            url = "https://api.replicate.com/v1/models/stability-ai/stable-video-diffusion-img2vid-xt/predictions"
            resp = requests.post(
                url,
                headers=_headers(),
                json={
                    "input": {
                        "input_image": data_uri,
                        "video_length": "25_frames_with_svd_xt",
                        "sizing_strategy": "maintain_aspect_ratio",
                        "motion_bucket_id": 80,
                        "cond_aug": 0.02,
                        "fps": 12,
                    }
                },
                timeout=600,
            )
            resp.raise_for_status()
            pred = resp.json()
            get_url = pred["urls"]["get"]
            while pred.get("status") not in {"succeeded", "failed", "canceled"}:
                time.sleep(3)
                poll = requests.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
                poll.raise_for_status()
                pred = poll.json()
            if pred.get("status") == "succeeded":
                video_url = pred["output"]
                tmp = output_path.with_suffix(".raw.mp4")
                download_file(video_url, tmp)
                _fit_clip_duration(tmp, output_path, seconds)
                tmp.unlink(missing_ok=True)
                return output_path
        except Exception as exc:
            print(f"SVD fallback to Ken Burns: {exc}")

    _ken_burns_clip(image_path, output_path, seconds)
    return output_path


def _fit_clip_duration(src: Path, dest: Path, seconds: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(src),
            "-t",
            str(seconds),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        check=True,
        capture_output=True,
    )


def _ken_burns_clip(image_path: Path, output_path: Path, seconds: float) -> None:
    frames = max(int(seconds * 30), 30)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-vf",
            (
                f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"zoompan=z='min(zoom+0.0012,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s=1080x1920:fps=30"
            ),
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
