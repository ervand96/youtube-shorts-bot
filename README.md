# YouTube Shorts Bot — AI Kids Cartoon Stories

Automated daily pipeline for creating and publishing YouTube Shorts.

## Pipeline

1. **Research** — find trending kids cartoon / bedtime story topics
2. **Script** — write 30–60 second script (simple English)
3. **Voice** — generate voiceover (edge-tts or ElevenLabs)
4. **Video** — assemble 9:16 vertical video with ffmpeg
5. **SEO** — title, description, tags, hashtags
6. **Upload** — publish Public to YouTube
7. **Analytics** — log metrics and learn from top performers

## Directories

- `scripts/` — daily scripts
- `audio/` — voiceover files
- `videos/` — rendered Shorts
- `analytics/` — performance logs and insights
- `assets/` — images, fonts, overlays

## Required secrets

Set these in Cursor Automations → Secrets:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `ELEVENLABS_API_KEY` (optional; falls back to edge-tts)

## Setup

```bash
pip install -r requirements.txt
# Authenticate YouTube OAuth once locally to obtain refresh token
python scripts/setup_youtube_auth.py
```
