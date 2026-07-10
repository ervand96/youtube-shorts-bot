#!/usr/bin/env python3
"""Show which YouTube channel each OAuth profile can access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import YOUTUBE_CHANNELS, resolve_channel, token_path_for
from scripts.youtube_client import whoami


def main() -> None:
    parser = argparse.ArgumentParser(description="Show authenticated YouTube channel(s)")
    parser.add_argument("--channel", help="One profile (benny|kinogo). Default: try all.")
    args = parser.parse_args()

    keys = [resolve_channel(args.channel)["key"]] if args.channel else list(YOUTUBE_CHANNELS)
    results = []
    for key in keys:
        path = token_path_for(key)
        try:
            info = whoami(key)
            info["token_file"] = str(path)
            info["token_exists"] = path.exists()
            results.append(info)
            print(f"OK  {key:8s} → {info['title']} ({info.get('customUrl')}) subs={info['subs']}")
        except Exception as exc:
            results.append({"profile": key, "error": str(exc), "token_exists": path.exists()})
            print(f"ERR {key:8s} → {exc}")

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
