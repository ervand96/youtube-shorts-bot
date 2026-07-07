#!/usr/bin/env python3
"""Upload rendered Short to YouTube as Public."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ANALYTICS_DIR, VIDEOS_DIR, ensure_dirs
from scripts.youtube_client import get_youtube_service


def load_metadata(metadata_path: Path) -> dict:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = ["title", "description", "tags"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"Metadata missing fields: {missing}")
    return data


def upload_video(video_path: Path, metadata: dict) -> dict:
    youtube = get_youtube_service()
    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": str(metadata.get("categoryId", "24")),
        },
        "status": {
            "privacyStatus": metadata.get("privacyStatus", "public"),
            "selfDeclaredMadeForKids": True,
        },
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}%")

    video_id = response["id"]
    return {
        "video_id": video_id,
        "url": f"https://youtube.com/shorts/{video_id}",
        "title": metadata["title"],
        "privacyStatus": body["status"]["privacyStatus"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Short to YouTube")
    parser.add_argument("--date", required=True)
    parser.add_argument("--metadata", help="Metadata JSON path override")
    args = parser.parse_args()

    ensure_dirs()
    video_path = VIDEOS_DIR / f"{args.date}.mp4"
    metadata_path = Path(args.metadata) if args.metadata else VIDEOS_DIR / f"{args.date}-metadata.json"
    upload_log = ANALYTICS_DIR / f"{args.date}-upload.json"

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not metadata_path.exists():
        raise FileNotFoundError(metadata_path)

    metadata = load_metadata(metadata_path)
    result = upload_video(video_path, metadata)
    upload_log.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
