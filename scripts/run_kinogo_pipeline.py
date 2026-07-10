#!/usr/bin/env python3
"""Process Kino Go TV queue: analyze clip → highlight Short → upload."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ANALYTICS_DIR, VIDEOS_DIR, ensure_dirs

QUEUE_PATH = ROOT / "config" / "kinogo_queue.json"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def next_file_id() -> str:
    day = date.today().isoformat()
    n = 1
    while (VIDEOS_DIR / f"kinogo-{day}-{n}.mp4").exists():
        n += 1
    return f"kinogo-{day}-{n}"


def load_queue() -> dict:
    if not QUEUE_PATH.exists():
        raise FileNotFoundError(f"Missing queue: {QUEUE_PATH}")
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def save_queue(data: dict) -> None:
    QUEUE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Kino Go TV movie Shorts pipeline")
    parser.add_argument("--url", help="Process one URL immediately (ignores queue)")
    parser.add_argument("--hook", help="Hook text for --url run")
    parser.add_argument("--title", help="Title hint for --url run")
    parser.add_argument("--music", help="Music credit label")
    parser.add_argument("--music-url", help="Optional background music URL")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Show next job only")
    args = parser.parse_args()

    ensure_dirs()
    py = sys.executable
    scripts = ROOT / "scripts"

    if args.url:
        job = {
            "url": args.url,
            "hook": args.hook,
            "title_hint": args.title,
            "music": args.music,
        }
        queue = None
    else:
        queue = load_queue()
        pending = queue.get("pending") or []
        if not pending:
            print(json.dumps({"status": "idle", "message": "No pending URLs in config/kinogo_queue.json"}))
            return
        job = pending[0]
        if args.dry_run:
            print(json.dumps({"status": "dry_run", "next": job}, indent=2))
            return

    file_id = next_file_id()
    cmd = [py, str(scripts / "build_movie_short.py"), "--id", file_id, "--url", job["url"]]
    if job.get("hook"):
        cmd.extend(["--hook", job["hook"]])
    if job.get("title_hint"):
        cmd.extend(["--title", job["title_hint"]])
    if job.get("music"):
        cmd.extend(["--music", job["music"]])
    if job.get("music_url"):
        cmd.extend(["--music-url", job["music_url"]])

    run(cmd)

    if not args.skip_upload:
        run([py, str(scripts / "upload_youtube.py"), "--id", file_id, "--channel", "kinogo"])
        run([py, str(scripts / "fetch_analytics.py"), "--id", file_id, "--channel", "kinogo"])

    if queue is not None:
        queue.setdefault("processed", []).append({**job, "file_id": file_id})
        queue["pending"] = queue["pending"][1:]
        save_queue(queue)

    result = {
        "status": "ok",
        "file_id": file_id,
        "video": str(VIDEOS_DIR / f"{file_id}.mp4"),
        "upload_log": str(ANALYTICS_DIR / f"{file_id}-upload.json"),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
