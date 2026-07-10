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

# Kino Go TV movie edits — 1080p vertical Shorts (matches channel style)
KINOGO_VIDEO_WIDTH = 1080
KINOGO_VIDEO_HEIGHT = 1920

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Multi-channel OAuth profiles. Each keeps its own token + refresh env var.
YOUTUBE_CHANNELS = {
    "benny": {
        "key": "benny",
        "label": "Benny's Story World",
        "token_file": "token.json",  # legacy default path
        "refresh_env": "YOUTUBE_REFRESH_TOKEN",
    },
    "kinogo": {
        "key": "kinogo",
        "label": "Kino Go TV",
        "token_file": "token-kinogo.json",
        "refresh_env": "YOUTUBE_KINOGO_REFRESH_TOKEN",
    },
}

_CHANNEL_ALIASES = {
    "benny": "benny",
    "kids": "benny",
    "default": "benny",
    "kinogo": "kinogo",
    "kino": "kinogo",
    "kino_gotv": "kinogo",
    "kino-go-tv": "kinogo",
    "kino go tv": "kinogo",
}


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (does not override existing)."""
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_channel(name: str | None = None) -> dict:
    key = _CHANNEL_ALIASES.get((name or "benny").strip().lower(), "")
    if not key:
        known = ", ".join(sorted(YOUTUBE_CHANNELS))
        raise ValueError(f"Unknown YouTube channel '{name}'. Use one of: {known}")
    return YOUTUBE_CHANNELS[key]


def token_path_for(channel: str | None = None) -> Path:
    meta = resolve_channel(channel)
    return CREDENTIALS_DIR / meta["token_file"]


def ensure_dirs() -> None:
    for path in (SCRIPTS_DIR, AUDIO_DIR, VIDEOS_DIR, ANALYTICS_DIR, ASSETS_DIR, CREDENTIALS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_env(name: str, default: str = "") -> str:
    load_dotenv()
    return os.environ.get(name, default).strip()


def use_premium_video() -> bool:
    """Premium 3D costs money on Replicate. Default is free/basic until monetization."""
    mode = get_env("VIDEO_MODE", "free").lower()
    if mode in {"free", "basic", "0", "false", "no"}:
        return False
    if mode in {"premium", "3d", "paid", "1", "true", "yes"}:
        return bool(get_env("REPLICATE_API_TOKEN"))
    return False


def date_paths(date_str: str) -> dict[str, Path]:
    return file_paths(date_str)


def file_paths(file_id: str) -> dict[str, Path]:
    return {
        "script": SCRIPTS_DIR / f"{file_id}-topic.md",
        "audio": AUDIO_DIR / f"{file_id}.mp3",
        "video": VIDEOS_DIR / f"{file_id}.mp4",
        "metadata": VIDEOS_DIR / f"{file_id}-metadata.json",
        "upload_log": ANALYTICS_DIR / f"{file_id}-upload.json",
        "stats": ANALYTICS_DIR / f"{file_id}-stats.json",
        "summary": ANALYTICS_DIR / f"{file_id}-summary.md",
        "error": ANALYTICS_DIR / f"{file_id}-error.md",
    }
