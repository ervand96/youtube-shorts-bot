#!/usr/bin/env python3
"""One-time OAuth setup to obtain YouTube refresh token."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import CLIENT_SECRETS_PATH, CREDENTIALS_DIR, TOKEN_PATH, YOUTUBE_SCOPES, ensure_dirs, get_env
from scripts.youtube_client import save_client_secrets_from_env


def main() -> None:
    ensure_dirs()
    save_client_secrets_from_env()

    if not CLIENT_SECRETS_PATH.exists():
        print("Missing credentials. Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env or environment.")
        print("Or place Google OAuth client JSON at credentials/client_secrets.json")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), YOUTUBE_SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved token to {TOKEN_PATH}")

    if creds.refresh_token:
        print("\nAdd this to Cursor Automations Secrets:")
        print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    else:
        print("Warning: no refresh token returned. Re-run with consent prompt.")


if __name__ == "__main__":
    main()
