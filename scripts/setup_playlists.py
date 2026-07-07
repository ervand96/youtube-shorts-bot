#!/usr/bin/env python3
"""Create professional playlists and channel sections."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
        "match": ["learn", "colors", "numbers", "preschool", "educational"],
    },
    {
        "title": "Moral Stories for Kids",
        "description": "Sweet moral lessons about sharing, kindness, and friendship.",
        "keywords": ["moral", "sharing", "kindness", "caring"],
        "match": ["sharing", "moral", "caring", "picnic", "lesson", "kind"],
    },
]


def get_channel_id(youtube) -> str:
    return youtube.channels().list(part="id", mine=True).execute()["items"][0]["id"]


def get_or_create_playlist(youtube, channel_id: str, spec: dict) -> str:
    existing = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
    for item in existing.get("items", []):
        if item["snippet"]["title"] == spec["title"]:
            return item["id"]

    created = (
        youtube.playlists()
        .insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": spec["title"],
                    "description": spec["description"],
                    "tags": spec["keywords"],
                },
                "status": {"privacyStatus": "public"},
            },
        )
        .execute()
    )
    pid = created["id"]
    print(f"Created playlist: {spec['title']} ({pid})")
    time.sleep(3)
    return pid


def list_channel_videos(youtube) -> list[dict]:
    channel_id = get_channel_id(youtube)
    uploads = (
        youtube.channels().list(part="contentDetails", id=channel_id).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )
    items = []
    token = None
    while True:
        resp = (
            youtube.playlistItems()
            .list(part="snippet", playlistId=uploads, maxResults=50, pageToken=token)
            .execute()
        )
        for it in resp.get("items", []):
            sn = it["snippet"]
            items.append({"id": sn["resourceId"]["videoId"], "title": sn["title"].lower()})
        token = resp.get("nextPageToken")
        if not token:
            break
    return items


def playlist_has_video(youtube, playlist_id: str, video_id: str) -> bool:
    token = None
    while True:
        resp = youtube.playlistItems().list(part="snippet", playlistId=playlist_id, maxResults=50, pageToken=token).execute()
        for it in resp.get("items", []):
            if it["snippet"]["resourceId"]["videoId"] == video_id:
                return True
        token = resp.get("nextPageToken")
        if not token:
            return False


def add_video_to_playlist(youtube, playlist_id: str, video_id: str) -> None:
    try:
        if playlist_has_video(youtube, playlist_id, video_id):
            return
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
        ).execute()
    except Exception as exc:
        print(f"Could not add {video_id} to {playlist_id}: {exc}")


def match_playlist(title: str, spec: dict) -> bool:
    return any(k in title for k in spec["match"])


def setup_channel_sections(youtube, channel_id: str, playlist_ids: list[str]) -> None:
    existing = youtube.channelSections().list(part="snippet,contentDetails", channelId=channel_id).execute()
    if existing.get("items"):
        print("Channel sections already exist, skipping")
        return

    youtube.channelSections().insert(
        part="snippet,contentDetails",
        body={
            "snippet": {"type": "singlePlaylist", "style": "horizontalRow", "title": "Nursery Rhymes", "position": 1},
            "contentDetails": {"playlists": [playlist_ids[0]]},
        },
    ).execute()
    youtube.channelSections().insert(
        part="snippet,contentDetails",
        body={
            "snippet": {"type": "singlePlaylist", "style": "horizontalRow", "title": "Bedtime Stories", "position": 2},
            "contentDetails": {"playlists": [playlist_ids[1]]},
        },
    ).execute()


def main() -> None:
    youtube = get_youtube_service()
    channel_id = get_channel_id(youtube)
    videos = list_channel_videos(youtube)
    playlist_ids = []

    for spec in PLAYLISTS:
        pid = get_or_create_playlist(youtube, channel_id, spec)
        playlist_ids.append(pid)
        added = 0
        for video in videos:
            if match_playlist(video["title"], spec):
                add_video_to_playlist(youtube, pid, video["id"])
                added += 1
        print(f"Playlist '{spec['title']}': {added} videos")

    try:
        setup_channel_sections(youtube, channel_id, playlist_ids)
        print("Channel sections created")
    except Exception as exc:
        print(f"Channel sections skipped: {exc}")

    print("Professional playlists ready")


if __name__ == "__main__":
    main()
