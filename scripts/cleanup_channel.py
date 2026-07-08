#!/usr/bin/env python3
"""Remove duplicate Shorts — keep the latest Jul 8 batch of 5."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.setup_playlists import list_channel_videos
from scripts.youtube_client import get_youtube_service

# Latest Jul 8 batch (keep these)
KEEP_VIDEO_IDS = {
    "wthP4In4IWc",  # Good Morning (new renderer)
    "pBHQ7IJ9pJ4",  # Bedtime
    "RbXFozAurTw",  # ABC
    "qFB1WkEF__4",  # Kindness
    "U3Ia6x6UNqw",  # Old MacDonald
}


def delete_video(youtube, video_id: str) -> None:
    youtube.videos().delete(id=video_id).execute()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Delete duplicate channel videos")
    parser.add_argument("--dry-run", action="store_true", help="List only, do not delete")
    args = parser.parse_args()

    youtube = get_youtube_service()
    videos = list_channel_videos(youtube)
    to_delete = [v for v in videos if v["id"] not in KEEP_VIDEO_IDS]
    kept = [v for v in videos if v["id"] in KEEP_VIDEO_IDS]

    print(f"Channel has {len(videos)} videos — keeping {len(kept)}, deleting {len(to_delete)}")
    for v in kept:
        print(f"  KEEP  {v['id']}  {v['title']}")
    for v in to_delete:
        print(f"  DELETE {v['id']}  {v['title']}")

    if args.dry_run:
        print("\nDry run — nothing deleted.")
        return

    log = ROOT / "analytics" / "cleanup-deleted.json"
    deleted = []
    for v in to_delete:
        try:
            delete_video(youtube, v["id"])
            deleted.append(v)
            print(f"Deleted: {v['id']}")
        except Exception as exc:
            print(f"Failed {v['id']}: {exc}")

    log.write_text(json.dumps({"kept": list(KEEP_VIDEO_IDS), "deleted": deleted}, indent=2), encoding="utf-8")
    print(f"\nDone. Log: {log}")


if __name__ == "__main__":
    main()
