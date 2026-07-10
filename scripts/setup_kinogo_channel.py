#!/usr/bin/env python3
"""Optimize Kino Go TV channel for views: branding, SEO, playlists, cleanup."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.kinogo_seo import (  # noqa: E402
    CHANNEL_DESCRIPTION,
    CHANNEL_KEYWORDS,
    CHANNEL_TITLE,
    PLAYLISTS,
    SECTION_SPECS,
    build_video_metadata,
    is_off_niche,
)
from scripts.setup_playlists import (  # noqa: E402
    add_video_to_playlist,
    get_channel_id,
    get_or_create_playlist,
    list_channel_videos,
    match_playlist,
)
from scripts.youtube_client import get_youtube_service


def list_videos_full(youtube) -> list[dict]:
    channel_id = get_channel_id(youtube)
    uploads = (
        youtube.channels()
        .list(part="contentDetails", id=channel_id)
        .execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )
    ids: list[str] = []
    titles: dict[str, str] = {}
    token = None
    while True:
        kw = {"part": "contentDetails,snippet", "playlistId": uploads, "maxResults": 50}
        if token:
            kw["pageToken"] = token
        page = youtube.playlistItems().list(**kw).execute()
        for it in page.get("items", []):
            vid = it["contentDetails"]["videoId"]
            ids.append(vid)
            titles[vid] = it["snippet"]["title"]
        token = page.get("nextPageToken")
        if not token:
            break

    rows = []
    for i in range(0, len(ids), 50):
        batch = ids[i : i + 50]
        resp = youtube.videos().list(part="snippet,status,statistics", id=",".join(batch)).execute()
        for v in resp.get("items", []):
            vid = v["id"]
            sn = v["snippet"]
            st = v["status"]
            rows.append(
                {
                    "id": vid,
                    "title": sn["title"],
                    "description": sn.get("description") or "",
                    "tags": sn.get("tags") or [],
                    "categoryId": sn.get("categoryId"),
                    "privacy": st.get("privacyStatus"),
                    "views": int(v["statistics"].get("viewCount", 0)),
                    "off_niche": is_off_niche(sn["title"]),
                }
            )
    return rows


def update_channel_branding(youtube, channel_id: str, dry_run: bool) -> None:
    body = {
        "id": channel_id,
        "brandingSettings": {
            "channel": {
                "title": CHANNEL_TITLE,
                "description": CHANNEL_DESCRIPTION,
                "keywords": CHANNEL_KEYWORDS,
                "defaultTab": "featured",
                "showRelatedChannels": True,
                "showBrowseView": True,
            },
        },
    }
    if dry_run:
        print("[dry-run] Would update channel description + keywords")
        return
    youtube.channels().update(part="brandingSettings", body=body).execute()
    # Explicitly NOT Made for Kids — general audience film channel
    youtube.channels().update(
        part="status",
        body={"id": channel_id, "status": {"selfDeclaredMadeForKids": False}},
    ).execute()
    print("Channel branding updated (Film channel, NOT Made for Kids)")


def fix_video(youtube, video: dict, dry_run: bool) -> dict:
    action = {"id": video["id"], "title": video["title"], "actions": []}

    if video["off_niche"] and video["privacy"] == "public":
        action["actions"].append("set_private_off_niche")
        if not dry_run:
            youtube.videos().update(
                part="status",
                body={
                    "id": video["id"],
                    "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
                },
            ).execute()
        return action

    if video["privacy"] != "public":
        return action

    meta = build_video_metadata(video["title"], video["description"])
    needs_update = (
        video["categoryId"] != meta["categoryId"]
        or len(video["tags"]) < 5
        or len(video["description"]) < 80
    )
    if not needs_update:
        action["actions"].append("skip_already_ok")
        return action

    action["actions"].append("update_seo")
    action["new_tags"] = meta["tags"]
    if not dry_run:
        youtube.videos().update(
            part="snippet",
            body={
                "id": video["id"],
                "snippet": {
                    "title": video["title"],
                    "description": meta["description"],
                    "categoryId": meta["categoryId"],
                    "tags": meta["tags"],
                },
            },
        ).execute()
        time.sleep(0.5)
    return action


def sync_playlists(youtube, channel_id: str, videos: list[dict], dry_run: bool) -> list[str]:
    playlist_ids: list[str] = []
    title_map = {v["id"]: v["title"].lower() for v in videos}

    for spec in PLAYLISTS:
        if dry_run:
            print(f"[dry-run] Would create/sync playlist: {spec['title']}")
            playlist_ids.append("dry-run")
            continue
        pid = get_or_create_playlist(youtube, channel_id, spec)
        playlist_ids.append(pid)
        added = 0
        for vid in spec.get("video_ids", []):
            if vid in title_map:
                add_video_to_playlist(youtube, pid, vid)
                added += 1
        for vid, title in title_map.items():
            if match_playlist(title, spec):
                add_video_to_playlist(youtube, pid, vid)
                added += 1
        print(f"Playlist '{spec['title']}': synced ({added} videos)")
        time.sleep(2)
    return playlist_ids


def ensure_home_sections(youtube, channel_id: str, playlist_ids: list[str], dry_run: bool) -> None:
    if dry_run:
        print("[dry-run] Would create channel home sections")
        return
    existing = youtube.channelSections().list(part="snippet,contentDetails", channelId=channel_id).execute()
    if existing.get("items"):
        print("Channel sections already exist — skipping")
        return
    for idx, (title, pl_idx) in enumerate(SECTION_SPECS):
        if pl_idx >= len(playlist_ids):
            continue
        youtube.channelSections().insert(
            part="snippet,contentDetails",
            body={
                "snippet": {
                    "type": "singlePlaylist",
                    "style": "horizontalRow",
                    "title": title,
                    "position": idx,
                },
                "contentDetails": {"playlists": [playlist_ids[pl_idx]]},
            },
        ).execute()
        time.sleep(3)
    print("Channel home sections created")


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize Kino Go TV for more views")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--skip-playlists", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

    youtube = get_youtube_service("kinogo")
    channel_id = get_channel_id(youtube)
    print(f"Kino Go TV ({channel_id}) — {'DRY RUN' if dry_run else 'APPLYING'}")

    update_channel_branding(youtube, channel_id, dry_run)
    videos = list_videos_full(youtube)
    actions = []
    for video in videos:
        result = fix_video(youtube, video, dry_run)
        if result["actions"]:
            actions.append(result)
            print(f"  {video['id']}: {result['actions']} — {video['title'][:50]}")

    playlist_ids = []
    if not args.skip_playlists:
        playlist_ids = sync_playlists(youtube, channel_id, videos, dry_run)
        ensure_home_sections(youtube, channel_id, playlist_ids, dry_run)

    log_path = ROOT / "analytics" / "kinogo-optimize-log.json"
    log_path.write_text(
        json.dumps(
            {
                "dry_run": dry_run,
                "channel_id": channel_id,
                "video_actions": actions,
                "playlist_count": len(playlist_ids),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nDone. Log: {log_path}")
    if dry_run:
        print("Re-run with --apply to push changes live.")


if __name__ == "__main__":
    main()
