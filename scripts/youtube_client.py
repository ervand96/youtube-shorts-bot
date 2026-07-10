#!/usr/bin/env python3
"""Shared YouTube API credential helpers (multi-channel)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import (  # noqa: E402
    CLIENT_SECRETS_PATH,
    CREDENTIALS_DIR,
    YOUTUBE_SCOPES,
    ensure_dirs,
    get_env,
    load_dotenv,
    resolve_channel,
    token_path_for,
)


def _client_config_from_env() -> dict | None:
    client_id = get_env("YOUTUBE_CLIENT_ID")
    client_secret = get_env("YOUTUBE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _refresh_token_env_key(channel: str) -> str:
    meta = resolve_channel(channel)
    return meta["refresh_env"]


def load_credentials(channel: str = "benny") -> Credentials:
    load_dotenv()
    ensure_dirs()
    meta = resolve_channel(channel)
    path = token_path_for(channel)
    refresh_env = meta["refresh_env"]

    creds: Credentials | None = None
    if path.exists():
        creds = Credentials.from_authorized_user_file(str(path), YOUTUBE_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json())

    if creds and creds.valid:
        return creds

    refresh_token = get_env(refresh_env)
    # Benny/default also accepts legacy YOUTUBE_REFRESH_TOKEN if alias-specific missing
    if not refresh_token and meta["key"] == "benny":
        refresh_token = get_env("YOUTUBE_REFRESH_TOKEN")

    client_config = _client_config_from_env()
    if refresh_token and client_config:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=client_config["installed"]["token_uri"],
            client_id=client_config["installed"]["client_id"],
            client_secret=client_config["installed"]["client_secret"],
            scopes=YOUTUBE_SCOPES,
        )
        creds.refresh(Request())
        path.write_text(creds.to_json())
        return creds

    raise RuntimeError(
        f"YouTube credentials missing for channel '{meta['key']}'. "
        f"Run: .venv/bin/python scripts/setup_youtube_auth.py --channel {meta['key']}\n"
        f"Or set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, {refresh_env}."
    )


def get_youtube_service(channel: str = "benny"):
    return build("youtube", "v3", credentials=load_credentials(channel))


def save_client_secrets_from_env() -> None:
    load_dotenv()
    config = _client_config_from_env()
    if config:
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        CLIENT_SECRETS_PATH.write_text(json.dumps(config, indent=2))


def whoami(channel: str = "benny") -> dict:
    """Return the authenticated channel identity for a profile."""
    youtube = get_youtube_service(channel)
    resp = youtube.channels().list(part="snippet,statistics,status", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        raise RuntimeError(f"No YouTube channel for profile '{channel}'")
    ch = items[0]
    return {
        "profile": resolve_channel(channel)["key"],
        "id": ch["id"],
        "title": ch["snippet"]["title"],
        "customUrl": ch["snippet"].get("customUrl"),
        "subs": ch["statistics"].get("subscriberCount"),
        "views": ch["statistics"].get("viewCount"),
        "videos": ch["statistics"].get("videoCount"),
        "madeForKids": ch["status"].get("madeForKids"),
    }
