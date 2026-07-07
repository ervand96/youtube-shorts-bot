#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "Ready. Run: .venv/bin/python scripts/run_pipeline.py --date $(date +%F) --skip-upload"
