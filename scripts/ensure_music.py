"""Generate royalty-free kids background music loops (no external assets needed)."""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import ASSETS_DIR

MUSIC_DIR = ASSETS_DIR / "music"

# note frequency Hz
NOTES = {
    "C3": 130.81,
    "D3": 146.83,
    "G3": 196.00,
    "A3": 220.00,
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "F4": 349.23,
    "G4": 392.0,
    "A4": 440.0,
    "B4": 493.88,
    "C5": 523.25,
    "D5": 587.33,
    "E5": 659.25,
}

STYLES: dict[str, list[tuple[str, float]]] = {
    "nursery": [
        ("C4", 0.35),
        ("E4", 0.35),
        ("G4", 0.35),
        ("C5", 0.35),
        ("G4", 0.35),
        ("E4", 0.35),
        ("C4", 0.7),
    ],
    "bedtime": [
        ("C4", 0.8),
        ("G4", 0.8),
        ("E4", 0.8),
        ("C4", 1.2),
        ("A4", 0.8),
        ("F4", 0.8),
        ("C4", 1.6),
    ],
    "learning": [
        ("C5", 0.25),
        ("D5", 0.25),
        ("E5", 0.25),
        ("C5", 0.25),
        ("G4", 0.25),
        ("E4", 0.25),
        ("C4", 0.5),
    ],
    "moral": [
        ("E4", 0.45),
        ("G4", 0.45),
        ("C5", 0.45),
        ("G4", 0.45),
        ("E4", 0.45),
        ("D4", 0.45),
        ("C4", 0.9),
    ],
    "animals": [
        ("G4", 0.3),
        ("G4", 0.3),
        ("C5", 0.3),
        ("G4", 0.3),
        ("E4", 0.3),
        ("F4", 0.3),
        ("G4", 0.6),
    ],
    "cinematic": [
        ("C3", 1.6),
        ("G3", 1.6),
        ("A3", 1.2),
        ("G3", 1.6),
        ("C3", 2.0),
        ("D3", 1.2),
        ("G3", 2.4),
    ],
}


def _tone(freq: float, duration: float, volume: float = 0.22) -> list[float]:
    sample_rate = 44100
    samples = int(sample_rate * duration)
    out: list[float] = []
    for i in range(samples):
        t = i / sample_rate
        attack = min(1.0, t / 0.02)
        release = min(1.0, (duration - t) / 0.05) if duration > t else 1.0
        env = attack * release
        sample = (
            math.sin(2 * math.pi * freq * t) * 0.65
            + math.sin(2 * math.pi * freq * 2 * t) * 0.2
            + math.sin(2 * math.pi * freq * 3 * t) * 0.08
        ) * volume * env
        out.append(sample)
    return out


def _render_wav(pattern: list[tuple[str, float]], loop_seconds: float = 48.0) -> list[float]:
    sample_rate = 44100
    target = int(sample_rate * loop_seconds)
    audio: list[float] = []
    while len(audio) < target:
        for note, dur in pattern:
            audio.extend(_tone(NOTES[note], dur))
    return audio[:target]


def _write_wav(path: Path, audio: list[float]) -> None:
    sample_rate = 44100
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for sample in audio:
            clamped = max(-1.0, min(1.0, sample))
            frames.extend(struct.pack("<h", int(clamped * 32767 * 0.85)))
        wf.writeframes(frames)


def ensure_music(category: str = "nursery") -> Path:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    mp3_path = MUSIC_DIR / f"{category}.mp3"
    if mp3_path.exists():
        return mp3_path

    wav_path = MUSIC_DIR / f"{category}.wav"
    pattern = STYLES.get(category, STYLES["nursery"])
    _write_wav(wav_path, _render_wav(pattern))
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "4", str(mp3_path)],
        check=True,
        capture_output=True,
    )
    wav_path.unlink(missing_ok=True)
    return mp3_path


if __name__ == "__main__":
    for cat in STYLES:
        path = ensure_music(cat)
        print(f"Generated {path}")
