# YouTube Shorts Bot — AI Kids Cartoon Stories

Automated daily pipeline for creating and publishing YouTube Shorts.

## Pipeline

1. **Research** — find trending kids cartoon / bedtime story topics
2. **Script** — write 30–60 second script (simple English)
3. **Voice** — `scripts/generate_voice.py` (edge-tts or ElevenLabs)
4. **Video** — `scripts/build_video.py`
   - **Premium (default if token set):** AI 3D scenes via Replicate (Flux + motion)
   - **Basic fallback:** 2D cartoon animation
5. **SEO** — metadata JSON in `videos/YYYY-MM-DD-metadata.json`
6. **Upload** — `scripts/upload_youtube.py` (Public)
7. **Analytics** — `scripts/fetch_analytics.py`

## Premium 3D videos (NuNu TV style)

For professional 3D kids cartoon quality:

1. Create token at [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
2. Add to `.env` and Cursor Automation secrets:
   ```
   REPLICATE_API_TOKEN=r8_...
   ```
3. Pipeline auto-uses premium mode when token is set.

Each Short generates ~5 AI scenes (Flux 3D style) + motion clips.
Estimated cost: ~$0.10–0.30 per Short on Replicate.

Force modes:
```bash
python scripts/build_video.py --date 2026-07-08 --script scripts/....md --premium
python scripts/build_video.py --date 2026-07-08 --script scripts/....md --basic
```


```bash
cd ~/Projects/youtube-shorts-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET
python scripts/setup_youtube_auth.py
```

## Run one Short manually

```bash
# 1) Agent or you create:
#    scripts/2026-07-07-topic.md
#    videos/2026-07-07-metadata.json

# 2) Run full pipeline
python scripts/run_pipeline.py --date 2026-07-07

# Test without upload
python scripts/run_pipeline.py --date 2026-07-07 --skip-upload
```

## Individual steps

```bash
python scripts/generate_voice.py --date 2026-07-07 --script scripts/2026-07-07-topic.md
python scripts/build_video.py --date 2026-07-07 --script scripts/2026-07-07-topic.md
python scripts/upload_youtube.py --date 2026-07-07
python scripts/fetch_analytics.py --date 2026-07-07
```

## Cursor Automation secrets

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `ELEVENLABS_API_KEY` (optional)

Automation repo: `ervand96/youtube-shorts-bot`, branch `master`, schedule `09:00`.

## Directories

- `scripts/` — topic scripts + pipeline code
- `audio/` — voiceover MP3
- `videos/` — rendered Shorts + metadata JSON
- `analytics/` — upload logs, stats, learnings
- `assets/` — optional background music (`background.mp3`)
- `credentials/` — OAuth token (local only, gitignored)
