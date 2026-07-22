#!/usr/bin/env python3
"""Upload rendered Short to YouTube."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ANALYTICS_DIR, VIDEOS_DIR, ensure_dirs, resolve_channel
from scripts.seo_guardrails import assert_safe_metadata
from scripts.youtube_client import get_youtube_service


def load_metadata(metadata_path: Path, channel: str = "benny") -> dict:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = ["title", "description", "tags"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"Metadata missing fields: {missing}")
    if resolve_channel(channel)["key"] == "benny":
        assert_safe_metadata(data)
    return data


def upload_video(
    video_path: Path,
    metadata: dict,
    publish_at: str | None = None,
    channel: str = "benny",
) -> dict:
    youtube = get_youtube_service(channel)
    profile = resolve_channel(channel)
    if profile["key"] == "benny":
        assert_safe_metadata(metadata)
    status = {
        "privacyStatus": metadata.get("privacyStatus", "public"),
    }
    # Kids channel only — Kino Go TV is general-audience film content
    if profile["key"] == "benny":
        status["selfDeclaredMadeForKids"] = True
    else:
        status["selfDeclaredMadeForKids"] = metadata.get("madeForKids", False)
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    # Realistic AI/deepfake disclosure — only when metadata opts in (premium 3D).
    if metadata.get("containsSyntheticMedia") is True:
        status["containsSyntheticMedia"] = True

    if profile["key"] == "benny":
        category = str(metadata.get("categoryId", "24"))
    else:
        category = str(metadata.get("categoryId", "1"))

    snippet = {
        "title": metadata["title"][:100],
        "description": metadata["description"],
        "tags": metadata["tags"],
        "categoryId": category,
    }
    if profile["key"] == "benny":
        snippet["defaultLanguage"] = "en"
        snippet["defaultAudioLanguage"] = "en"

    body = {
        "snippet": snippet,
        "status": status,
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status_chunk, response = request.next_chunk()
        if status_chunk:
            print(f"Upload {int(status_chunk.progress() * 100)}%")

    video_id = response["id"]
    return {
        "video_id": video_id,
        "url": f"https://youtube.com/shorts/{video_id}",
        "title": metadata["title"],
        "privacyStatus": body["status"]["privacyStatus"],
        "publishAt": publish_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Short to YouTube")
    parser.add_argument("--id", help="File id e.g. 2026-07-09-1")
    parser.add_argument("--date", help="Legacy date id")
    parser.add_argument("--metadata", help="Metadata JSON path override")
    parser.add_argument("--publish-at", help="RFC3339 UTC schedule e.g. 2026-07-09T05:00:00Z")
    parser.add_argument("--channel", default="benny", help="OAuth profile: benny or kinogo")
    args = parser.parse_args()
    file_id = args.id or args.date
    if not file_id:
        raise SystemExit("Provide --id or --date")

    ensure_dirs()
    video_path = VIDEOS_DIR / f"{file_id}.mp4"
    metadata_path = Path(args.metadata) if args.metadata else VIDEOS_DIR / f"{file_id}-metadata.json"
    upload_log = ANALYTICS_DIR / f"{file_id}-upload.json"

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not metadata_path.exists():
        raise FileNotFoundError(metadata_path)

    metadata = load_metadata(metadata_path, channel=args.channel)
    result = upload_video(video_path, metadata, publish_at=args.publish_at, channel=args.channel)
    upload_log.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
