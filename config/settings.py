import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
AUDIO_DIR = ROOT / "audio"
VIDEOS_DIR = ROOT / "videos"
ANALYTICS_DIR = ROOT / "analytics"
ASSETS_DIR = ROOT / "assets"
CREDENTIALS_DIR = ROOT / "credentials"

TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CLIENT_SECRETS_PATH = CREDENTIALS_DIR / "client_secrets.json"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def ensure_dirs() -> None:
    for path in (SCRIPTS_DIR, AUDIO_DIR, VIDEOS_DIR, ANALYTICS_DIR, ASSETS_DIR, CREDENTIALS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def date_paths(date_str: str) -> dict[str, Path]:
    return {
        "script": SCRIPTS_DIR / f"{date_str}-topic.md",
        "audio": AUDIO_DIR / f"{date_str}.mp3",
        "video": VIDEOS_DIR / f"{date_str}.mp4",
        "metadata": VIDEOS_DIR / f"{date_str}-metadata.json",
        "upload_log": ANALYTICS_DIR / f"{date_str}-upload.json",
        "stats": ANALYTICS_DIR / f"{date_str}-stats.json",
        "summary": ANALYTICS_DIR / f"{date_str}-summary.md",
        "error": ANALYTICS_DIR / f"{date_str}-error.md",
    }
