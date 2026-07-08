#!/usr/bin/env python3
"""Complete YouTube channel setup: branding, watermark, playlists, home sections."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ASSETS_DIR
from scripts.setup_playlists import (
    add_video_to_playlist,
    get_channel_id,
    get_or_create_playlist,
    list_channel_videos,
    match_playlist,
)
from scripts.update_channel_branding import (
    CHANNEL_DESCRIPTION,
    CHANNEL_KEYWORDS,
    CHANNEL_TITLE,
    upload_banner,
)
from scripts.youtube_client import get_youtube_service

PLAYLISTS = [
    {
        "title": "Nursery Rhymes & Kids Songs",
        "description": "Sing-along nursery rhymes and fun kids songs from Benny's Story World!",
        "keywords": ["nursery rhymes", "kids songs", "sing along", "toddler"],
        "match": ["bus", "rainbow", "nursery", "rhyme", "farm", "animal", "song", "band"],
    },
    {
        "title": "Bedtime Stories for Kids",
        "description": "Gentle bedtime cartoon stories for ages 2-8. Sweet dreams!",
        "keywords": ["bedtime", "story", "sleepy", "star"],
        "match": ["bedtime", "sleepy", "star", "sleep", "dream"],
    },
    {
        "title": "Learning for Preschool",
        "description": "Fun educational Shorts — colors, numbers, ABC and more for preschoolers.",
        "keywords": ["learn", "colors", "numbers", "educational", "preschool"],
        "match": ["learn", "colors", "numbers", "preschool", "educational", "abc"],
    },
    {
        "title": "Moral Stories for Kids",
        "description": "Sweet moral lessons about sharing, kindness, and friendship.",
        "keywords": ["moral", "sharing", "kindness", "caring"],
        "match": ["sharing", "moral", "caring", "picnic", "lesson", "kind"],
    },
]

SECTION_SPECS = [
    ("Nursery Rhymes & Songs", 0),
    ("Bedtime Stories", 1),
    ("Learning for Kids", 2),
    ("Moral Stories", 3),
]


def update_branding(youtube, channel_id: str) -> None:
    branding_body = {
        "id": channel_id,
        "brandingSettings": {
            "channel": {
                "title": CHANNEL_TITLE,
                "description": CHANNEL_DESCRIPTION,
                "keywords": CHANNEL_KEYWORDS,
                "defaultTab": "featured",
                "showRelatedChannels": True,
                "showBrowseView": True,
                "unsubscribedTrailer": "",
            },
        },
    }
    banner = ASSETS_DIR / "channel-banner-safe-yt.jpg"
    if not banner.exists():
        banner = ASSETS_DIR / "channel-banner-yt.jpg"
    if banner.exists():
        try:
            branding_body["brandingSettings"]["image"] = {
                "bannerExternalUrl": upload_banner(youtube, banner)
            }
            print(f"Banner updated: {banner.name}")
        except Exception as exc:
            print(f"Banner skipped: {exc}")

    youtube.channels().update(part="brandingSettings", body=branding_body).execute()
    youtube.channels().update(
        part="status",
        body={"id": channel_id, "status": {"selfDeclaredMadeForKids": True}},
    ).execute()
    print("Branding, description, keywords, Made for Kids — OK")


def upload_watermark(youtube, channel_id: str) -> None:
    watermark = ASSETS_DIR / "channel-watermark-150.png"
    if not watermark.exists():
        print("Watermark file missing, skipped")
        return
    try:
        import requests

        from scripts.youtube_client import load_credentials

        creds = load_credentials()
        if not creds.valid:
            creds.refresh(__import__("google.auth.transport.requests", fromlist=["Request"]).Request())

        url = "https://www.googleapis.com/upload/youtube/v3/watermarks/set"
        params = {"channelId": channel_id}
        headers = {"Authorization": f"Bearer {creds.token}"}
        timing = json.dumps(
            {
                "timing": {
                    "type": "offsetFromStart",
                    "offsetMs": 0,
                    "durationMs": 3600000,
                },
                "position": {"type": "corner", "cornerPosition": "bottomRight"},
                "targetChannelId": channel_id,
            }
        )
        with watermark.open("rb") as fh:
            resp = requests.post(
                url,
                params=params,
                headers=headers,
                files={
                    "media": ("watermark.png", fh, "image/png"),
                    "metadata": (None, timing, "application/json"),
                },
                timeout=60,
            )
        resp.raise_for_status()
        print(f"Watermark uploaded (full video): {watermark.name}")
    except Exception as exc:
        print(f"Watermark failed (set manually in Studio): {exc}")


def sync_playlists(youtube, channel_id: str) -> list[str]:
    videos = list_channel_videos(youtube)
    playlist_ids: list[str] = []
    for spec in PLAYLISTS:
        pid = get_or_create_playlist(youtube, channel_id, spec)
        playlist_ids.append(pid)
        added = 0
        for video in videos:
            if match_playlist(video["title"], spec):
                add_video_to_playlist(youtube, pid, video["id"])
                added += 1
        print(f"Playlist '{spec['title']}': {added} videos synced")
        time.sleep(1)
    return playlist_ids


def ensure_home_sections(youtube, channel_id: str, playlist_ids: list[str]) -> None:
    existing = youtube.channelSections().list(part="snippet,contentDetails", channelId=channel_id).execute()
    titles = {item["snippet"].get("title", "") for item in existing.get("items", [])}

    for (title, idx), playlist_id in zip(SECTION_SPECS, playlist_ids):
        if title in titles:
            print(f"Section exists: {title}")
            continue
        try:
            youtube.channelSections().insert(
                part="snippet,contentDetails",
                body={
                    "snippet": {
                        "type": "singlePlaylist",
                        "style": "horizontalRow",
                        "title": title,
                        "position": idx,
                    },
                    "contentDetails": {"playlists": [playlist_id]},
                },
            ).execute()
            print(f"Section created: {title}")
            time.sleep(1)
        except Exception as exc:
            print(f"Section '{title}' skipped: {exc}")


def main() -> None:
    youtube = get_youtube_service()
    channel_id = get_channel_id(youtube)
    print(f"Channel: {CHANNEL_TITLE} ({channel_id})")

    update_branding(youtube, channel_id)
    upload_watermark(youtube, channel_id)
    playlist_ids = sync_playlists(youtube, channel_id)
    ensure_home_sections(youtube, channel_id, playlist_ids)

    print("\nDone. Check: https://youtube.com/@BennysStoryWorldKids")


if __name__ == "__main__":
    main()
