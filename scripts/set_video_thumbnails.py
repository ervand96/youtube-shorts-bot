#!/usr/bin/env python3
"""Upload custom thumbnails for channel Shorts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_thumbnail import generate_thumbnail
from scripts.youtube_client import get_youtube_service

# video_id -> local metadata id (for thumbnail generation)
VIDEO_META_MAP = {
    "wthP4In4IWc": "2026-07-08-1",
    "pBHQ7IJ9pJ4": "2026-07-08-2",
    "RbXFozAurTw": "2026-07-08-3",
    "qFB1WkEF__4": "2026-07-08-4",
    "U3Ia6x6UNqw": "2026-07-08-5",
}


def upload_thumbnail(youtube, video_id: str, image_path: Path) -> None:
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(image_path), mimetype="image/png", resumable=False),
    ).execute()


def main() -> None:
    youtube = get_youtube_service()
    thumbs_dir = ROOT / "assets" / "thumbnails"
    results = []

    for video_id, meta_id in VIDEO_META_MAP.items():
        meta_path = ROOT / "videos" / f"{meta_id}-metadata.json"
        thumb_path = thumbs_dir / f"{meta_id}.png"
        if not meta_path.exists():
            print(f"SKIP {video_id}: missing {meta_path}")
            continue
        generate_thumbnail(meta_path, thumb_path)
        try:
            upload_thumbnail(youtube, video_id, thumb_path)
            results.append({"video_id": video_id, "thumbnail": str(thumb_path), "status": "ok"})
            print(f"Thumbnail set: {video_id} <- {thumb_path.name}")
        except Exception as exc:
            results.append({"video_id": video_id, "status": "failed", "error": str(exc)})
            print(f"Thumbnail failed {video_id}: {exc}")

    log = ROOT / "analytics" / "thumbnails-upload.json"
    log.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Log: {log}")


if __name__ == "__main__":
    main()
