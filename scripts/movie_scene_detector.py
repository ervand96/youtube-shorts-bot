#!/usr/bin/env python3
"""Find the most engaging segment in a movie clip for a Short."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SceneCut:
    time: float


@dataclass
class HighlightWindow:
    start: float
    duration: float
    score: float
    scene_cuts: int
    peak_db: float


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )
    return float(out.strip())


def detect_scene_cuts(path: Path, threshold: float = 0.32) -> list[SceneCut]:
    """Parse ffmpeg scene filter output for cut timestamps."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(path),
        "-filter:v",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stderr
    cuts: list[SceneCut] = []
    for line in log.splitlines():
        if "pts_time:" not in line:
            continue
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            cuts.append(SceneCut(time=float(m.group(1))))
    return cuts


def segment_peak_db(path: Path, start: float, duration: float) -> float:
    """Louder segments often correlate with action/dialogue peaks."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-i",
        str(path),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", proc.stderr)
    if not m:
        return -40.0
    return float(m.group(1))


def pick_highlight(
    path: Path,
    target_duration: float = 38.0,
    min_duration: float = 28.0,
    max_duration: float = 50.0,
) -> HighlightWindow:
    total = probe_duration(path)
    if total <= max_duration:
        peak = segment_peak_db(path, 0, total)
        return HighlightWindow(start=0, duration=total, score=peak, scene_cuts=0, peak_db=peak)

    cuts = detect_scene_cuts(path)
    cut_times = [c.time for c in cuts if 0 < c.time < total - 5]

    best: HighlightWindow | None = None
    step = 2.0
    t = 0.0
    while t + min_duration <= total:
        dur = min(target_duration, total - t)
        dur = max(min_duration, min(dur, max_duration))
        end = t + dur
        cuts_in = sum(1 for ct in cut_times if t <= ct <= end)
        peak = segment_peak_db(path, t, dur)
        # Favor action density + loud peaks; penalize very quiet segments.
        score = cuts_in * 4.5 + (peak + 20) * 0.8
        if t < 3:
            score += 1.5  # slight preference for early hook
        window = HighlightWindow(start=t, duration=dur, score=score, scene_cuts=cuts_in, peak_db=peak)
        if best is None or window.score > best.score:
            best = window
        t += step

    assert best is not None
    return best
