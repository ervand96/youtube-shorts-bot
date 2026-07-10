#!/usr/bin/env python3
"""One-time OAuth setup to obtain YouTube refresh token (per channel)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import (  # noqa: E402
    CLIENT_SECRETS_PATH,
    YOUTUBE_CHANNELS,
    YOUTUBE_SCOPES,
    ensure_dirs,
    resolve_channel,
    token_path_for,
)
from scripts.youtube_client import save_client_secrets_from_env, whoami  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize a YouTube channel profile")
    parser.add_argument(
        "--channel",
        default="benny",
        help=f"Channel profile: {', '.join(sorted(YOUTUBE_CHANNELS))} (aliases: kino, kids)",
    )
    args = parser.parse_args()
    meta = resolve_channel(args.channel)

    ensure_dirs()
    save_client_secrets_from_env()

    if not CLIENT_SECRETS_PATH.exists():
        print("Missing credentials. Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env")
        print("Or place Google OAuth client JSON at credentials/client_secrets.json")
        sys.exit(1)

    token_path = token_path_for(meta["key"])
    print(f"Authorizing profile: {meta['key']} ({meta['label']})")
    print("Browser will open — sign in with the Google account that OWNS this YouTube channel.")
    print("If Google asks which channel/brand account, pick the correct one.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), YOUTUBE_SCOPES)
    # force consent so we always get a refresh_token; select_account lets you pick the right Google login
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    token_path.write_text(creds.to_json())
    print(f"\nSaved token to {token_path}")

    if creds.refresh_token:
        print("\nAdd this to .env (and Cursor Automation secrets if needed):")
        print(f"{meta['refresh_env']}={creds.refresh_token}")
    else:
        print("Warning: no refresh token returned. Re-run this command.")

    try:
        info = whoami(meta["key"])
        print("\nAuthenticated as:")
        print(f"  title: {info['title']}")
        print(f"  url:   https://youtube.com/{info.get('customUrl') or ('channel/' + info['id'])}")
        print(f"  id:    {info['id']}")
        print(f"  subs:  {info['subs']}  videos: {info['videos']}  views: {info['views']}")
    except Exception as exc:
        print(f"\nToken saved, but channel lookup failed: {exc}")


if __name__ == "__main__":
    main()
