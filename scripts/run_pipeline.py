#!/usr/bin/env python3
"""Run voice -> video -> upload -> analytics for a prepared script."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import SCRIPTS_DIR, VIDEOS_DIR, date_paths, ensure_dirs


def run_step(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full Shorts pipeline for one day")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--script", help="Script markdown path")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-analytics", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    paths = date_paths(args.date)
    script_path = Path(args.script) if args.script else paths["script"]
    metadata_path = paths["metadata"]

    if not script_path.exists():
        raise FileNotFoundError(f"Script required: {script_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata required: {metadata_path}")

    py = sys.executable
    scripts = ROOT / "scripts"

    run_step([py, str(scripts / "generate_voice.py"), "--date", args.date, "--script", str(script_path)])
    run_step(
        [
            py,
            str(scripts / "build_video.py"),
            "--date",
            args.date,
            "--script",
            str(script_path),
        ]
    )

    if not args.skip_upload:
        run_step([py, str(scripts / "upload_youtube.py"), "--date", args.date])
        if not args.skip_analytics:
            run_step([py, str(scripts / "fetch_analytics.py"), "--date", args.date])

    print(json.dumps({"status": "ok", "date": args.date, "video": str(paths["video"])}, indent=2))


if __name__ == "__main__":
    main()
