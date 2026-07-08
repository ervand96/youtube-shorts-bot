# AGENTS.md

## Cursor Cloud specific instructions

This is a Python (3.12) CLI pipeline that turns a topic markdown file into a
9:16 YouTube Short (voiceover + rendered video) and optionally uploads it and
fetches analytics. There is no web/GUI service — everything runs from the
terminal. Standard commands live in `README.md`.

### Environment
- Python deps are installed into a local virtualenv at `.venv` (kept out of git).
  The startup update script recreates/refreshes it, so run tools with
  `.venv/bin/python ...`.
- System deps already present in the base image: `ffmpeg`/`ffprobe` and the
  DejaVu fonts (`/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`, used by
  `scripts/build_video.py` for subtitles). `python3.12-venv` is also installed so
  `python3 -m venv` works.

### Running / testing the pipeline
- The offline, secret-free path is voice → video. Run it with:
  `.venv/bin/python scripts/run_pipeline.py --date <YYYY-MM-DD> --skip-upload`
  It requires `scripts/<date>-topic.md` and `videos/<date>-metadata.json` to
  exist (the repo ships `2026-07-07` samples).
- Voiceover (`scripts/generate_voice.py`) uses `edge-tts` by default, which makes
  an outbound call to Microsoft's TTS endpoint — it needs network egress. If
  `ELEVENLABS_API_KEY` is set it uses ElevenLabs instead.
- Generated media (`audio/*.mp3`, `videos/*.mp4`) is gitignored on purpose.

### Secrets / what cannot run without them
- `scripts/upload_youtube.py` and `scripts/fetch_analytics.py` require YouTube
  OAuth credentials (`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`,
  `YOUTUBE_REFRESH_TOKEN`). Without them these steps raise a clear
  "credentials missing" error; the voice+video steps still work with
  `--skip-upload`. Copy `.env.example` to `.env` to configure locally.

### Gotchas
- With the base image's ffmpeg, the frame-concat step in `build_video.py`
  produces a short/low-frame-count `.mp4` (the concat demuxer does not honor
  per-frame durations here). The pipeline still exits 0 and writes a valid,
  correctly-sized (1080x1920 h264+aac) file, and the Pillow subtitle rendering
  is correct. This is pre-existing app behavior, not an environment problem.
