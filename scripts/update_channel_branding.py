#!/usr/bin/env python3
"""Update YouTube channel branding for kids cartoon content."""

from __future__ import annotations

import sys
from pathlib import Path

from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ASSETS_DIR
from scripts.youtube_client import get_youtube_service

CHANNEL_TITLE = "Benny's Story World"
CHANNEL_DESCRIPTION = """Welcome to Benny's Story World!

Cute cartoon bedtime stories, moral tales, and fun adventures for kids ages 3-8.
Every Short brings a new friendly character, a gentle lesson, and a happy ending.

Perfect for bedtime, quiet time, and family viewing.
Simple English - easy for kids to follow.
Colorful cartoon stories made with love.

New kids stories every day!
Subscribe and join our story family.

#kids #bedtimestory #cartoon #children #moralstory #preschool #shorts #kidslearning
"""

CHANNEL_KEYWORDS = (
    "kids stories, bedtime stories, cartoon for kids, children stories, moral stories, "
    "preschool stories, kids shorts, english stories for kids, cute cartoon, "
    "bedtime cartoon, kids animation, family friendly, educational stories, "
    "story for children, toddler stories, kids youtube"
)


def upload_banner(youtube, banner_path: Path) -> str:
    media = MediaFileUpload(
        str(banner_path),
        mimetype="image/jpeg" if banner_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png",
        resumable=True,
    )
    return youtube.channelBanners().insert(media_body=media).execute()["url"]


def main() -> None:
    youtube = get_youtube_service()
    channel_id = youtube.channels().list(part="id", mine=True).execute()["items"][0]["id"]

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
            },
        },
    }

    for candidate in (
        ASSETS_DIR / "channel-banner-yt.jpg",
        ASSETS_DIR / "channel-banner-yt.png",
        ASSETS_DIR / "channel-banner.png",
    ):
        if candidate.exists():
            try:
                print(f"Uploading banner: {candidate}")
                branding_body["brandingSettings"]["image"] = {
                    "bannerExternalUrl": upload_banner(youtube, candidate)
                }
            except Exception as exc:
                print(f"Banner upload skipped: {exc}")
            break

    youtube.channels().update(part="brandingSettings", body=branding_body).execute()
    print("Updated description, keywords, and banner")

    youtube.channels().update(
        part="status",
        body={"id": channel_id, "status": {"selfDeclaredMadeForKids": True}},
    ).execute()
    print("Channel marked as Made for Kids")

    print(f"Target name: {CHANNEL_TITLE}")
    print(f"URL: https://youtube.com/channel/{channel_id}")
    print("Change display name manually: Studio -> Customization -> Basic info -> Name")
    avatar = ASSETS_DIR / "channel-avatar-yt.png"
    if avatar.exists():
        print(f"Avatar file: {avatar}")
        print("Upload avatar: Studio -> Customization -> Profile picture")


if __name__ == "__main__":
    main()
