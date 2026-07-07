#!/usr/bin/env python3
"""Run 5 Shorts per day with staggered publish times."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import SCRIPTS_DIR, VIDEOS_DIR, ensure_dirs

BATCH_CONFIG = ROOT / "config" / "daily_batch.json"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def file_id(day: str, slot: int) -> str:
    return f"{day}-{slot}"


def publish_at_iso(day: str, hour: int, tz_offset_hours: int = 4) -> str:
    local = datetime.strptime(f"{day} {hour:02d}:00:00", "%Y-%m-%d %H:%M:%S")
    utc = local - timedelta(hours=tz_offset_hours)
    return utc.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Produce 5 daily Shorts")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--slots", type=int, default=5)
    args = parser.parse_args()

    ensure_dirs()
    config = json.loads(BATCH_CONFIG.read_text(encoding="utf-8"))
    hours = config.get("publish_hours_local", [9, 11, 13, 15, 17])
    py = sys.executable
    scripts = ROOT / "scripts"
    results = []

    for slot in range(1, args.slots + 1):
        fid = file_id(args.date, slot)
        script_path = SCRIPTS_DIR / f"{fid}-topic.md"
        meta_path = VIDEOS_DIR / f"{fid}-metadata.json"

        if not script_path.exists():
            print(f"SKIP slot {slot}: missing {script_path}")
            continue
        if not meta_path.exists():
            print(f"SKIP slot {slot}: missing {meta_path}")
            continue

        run([py, str(scripts / "generate_voice.py"), "--id", fid, "--script", str(script_path)])
        run([py, str(scripts / "build_video.py"), "--id", fid, "--script", str(script_path), "--basic"])

        if not args.skip_upload:
            hour = hours[slot - 1] if slot - 1 < len(hours) else 9 + slot * 2
            pub = publish_at_iso(args.date, hour)
            run([py, str(scripts / "upload_youtube.py"), "--id", fid, "--publish-at", pub])
            run([py, str(scripts / "fetch_analytics.py"), "--date", fid])

        results.append(fid)

    print(json.dumps({"status": "ok", "date": args.date, "published": results}, indent=2))


if __name__ == "__main__":
    main()
