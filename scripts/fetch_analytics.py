#!/usr/bin/env python3
"""Fetch video stats and update analytics learnings."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ANALYTICS_DIR, ensure_dirs
from scripts.youtube_client import get_youtube_service


def fetch_stats(video_id: str, channel: str = "benny") -> dict:
    youtube = get_youtube_service(channel)
    response = (
        youtube.videos()
        .list(part="snippet,statistics", id=video_id)
        .execute()
    )
    items = response.get("items", [])
    if not items:
        raise RuntimeError(f"Video not found: {video_id}")

    item = items[0]
    stats = item.get("statistics", {})
    return {
        "video_id": video_id,
        "title": item["snippet"]["title"],
        "published_at": item["snippet"]["publishedAt"],
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def update_top_topics(stats: dict, metadata_path: Path | None) -> None:
    top_path = ANALYTICS_DIR / "top_topics.json"
    data = json.loads(top_path.read_text(encoding="utf-8")) if top_path.exists() else {"topics": [], "learnings": []}

    topic = metadata_path.stem.replace("-metadata", "") if metadata_path else stats["title"]
    data["topics"].append(
        {
            "topic": topic,
            "title": stats["title"],
            "views": stats["views"],
            "likes": stats["likes"],
            "recorded_at": stats["fetched_at"],
        }
    )
    data["topics"] = sorted(data["topics"], key=lambda x: x.get("views", 0), reverse=True)[:50]

    if stats["views"] >= 100:
        data["learnings"].append(f"Strong performer: {stats['title']} ({stats['views']} views)")
    data["learnings"] = data["learnings"][-30:]

    top_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_summary(date_str: str, stats: dict) -> None:
    summary_path = ANALYTICS_DIR / f"{date_str}-summary.md"
    bullets = [
        f"- Published: {stats['title']}",
        f"- Early views: {stats['views']}, likes: {stats['likes']}",
        "- Reuse hooks and morals from higher-view topics in analytics/top_topics.json",
    ]
    summary_path.write_text("# Daily summary\n\n" + "\n".join(bullets) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch YouTube video analytics")
    parser.add_argument("--id", help="File id e.g. 2026-07-09-1")
    parser.add_argument("--date", help="Legacy date id")
    parser.add_argument("--video-id", help="YouTube video ID override")
    parser.add_argument("--channel", default="benny", help="OAuth profile: benny or kinogo")
    args = parser.parse_args()
    file_id = args.id or args.date
    if not file_id:
        raise SystemExit("Provide --id or --date")

    ensure_dirs()
    upload_log = ANALYTICS_DIR / f"{file_id}-upload.json"
    stats_path = ANALYTICS_DIR / f"{file_id}-stats.json"
    metadata_path = ROOT / "videos" / f"{file_id}-metadata.json"

    video_id = args.video_id
    if not video_id:
        if not upload_log.exists():
            raise FileNotFoundError(f"Missing upload log: {upload_log}")
        video_id = json.loads(upload_log.read_text(encoding="utf-8"))["video_id"]

    stats = fetch_stats(video_id, channel=args.channel)
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    update_top_topics(stats, metadata_path if metadata_path.exists() else None)
    write_summary(file_id, stats)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
