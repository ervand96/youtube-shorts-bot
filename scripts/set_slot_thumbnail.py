#!/usr/bin/env python3
"""Generate + upload thumbnail for a slot after YouTube upload."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_thumbnail import generate_thumbnail
from scripts.youtube_client import get_youtube_service


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Set custom thumbnail for uploaded slot")
    parser.add_argument("--id", required=True, help="e.g. 2026-07-12-1")
    parser.add_argument("--channel", default="benny")
    args = parser.parse_args()

    upload_log = ROOT / "analytics" / f"{args.id}-upload.json"
    meta_path = ROOT / "videos" / f"{args.id}-metadata.json"
    thumb_path = ROOT / "assets" / "thumbnails" / f"{args.id}.png"

    if not upload_log.exists():
        print(f"SKIP thumbnail: missing {upload_log}")
        return
    if not meta_path.exists():
        print(f"SKIP thumbnail: missing {meta_path}")
        return

    video_id = json.loads(upload_log.read_text(encoding="utf-8")).get("video_id")
    if not video_id:
        print("SKIP thumbnail: no video_id in upload log")
        return

    generate_thumbnail(meta_path, thumb_path)
    youtube = get_youtube_service(args.channel)
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumb_path), mimetype="image/png", resumable=False),
        ).execute()
        print(f"Thumbnail set for {video_id}: {thumb_path.name}")
    except Exception as exc:
        print(f"Thumbnail skipped ({video_id}): {exc}")


if __name__ == "__main__":
    main()
