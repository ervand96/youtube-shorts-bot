#!/usr/bin/env python3
"""SEO helpers for Kino Go TV movie Shorts."""

from __future__ import annotations

import re

FILM_CATEGORY = "1"  # Film & Animation

BASE_TAGS = [
    "kino go tv",
    "movie shorts",
    "film edit",
    "cinema shorts",
    "movie clips",
    "shorts",
]

# Off-niche content that hurts channel focus and Shorts distribution.
OFF_NICHE_PATTERNS = [
    re.compile(r"roblox", re.I),
]

TITLE_RULES: list[tuple[re.Pattern[str], list[str], str]] = [
    (
        re.compile(r"passenger\s*57|bruce\s*payne|exactly", re.I),
        ["passenger 57", "bruce payne", "action movie", "90s action", "movie quote"],
        "Passenger 57 — iconic villain moment.",
    ),
    (
        re.compile(r"venom", re.I),
        ["venom 2018", "marvel", "superhero", "slowed edit", "movie edit"],
        "Venom (2018) slowed movie edit.",
    ),
    (
        re.compile(r"spider|peter|tony", re.I),
        ["spider-man", "marvel", "iron man", "emotional edit", "mcu"],
        "Spider-Man & Iron Man emotional movie edit.",
    ),
    (
        re.compile(r"tom\s*cruise|knight\s*and\s*day", re.I),
        ["tom cruise", "knight and day", "action comedy", "movie scene"],
        "Tom Cruise action moment from Knight and Day.",
    ),
    (
        re.compile(r"baby\s*shark", re.I),
        [],
        "",
    ),
]


def is_off_niche(title: str) -> bool:
    return any(p.search(title) for p in OFF_NICHE_PATTERNS)


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", text))


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        t = " ".join(tag.split()).strip()[:30]
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out[:15]


def build_video_metadata(title: str, existing_desc: str = "") -> dict:
    """Return snippet fields: description, tags, categoryId."""
    extra_tags: list[str] = []
    hook = title.strip()
    lang_note = ""

    for pattern, tags, note in TITLE_RULES:
        if pattern.search(title):
            extra_tags.extend(tags)
            if note:
                hook = note

    if has_cyrillic(title):
        extra_tags.extend(["кино", "фильм", "сериал", "shorts", "русское кино", "клип из фильма"])
        lang_note = "\n🇷🇺 Кино Shorts на русском — подпишись на Kino Go TV!"
    else:
        extra_tags.extend(["hollywood", "movie moment", "viral film clip"])
        lang_note = "\n🎬 Daily movie Shorts — subscribe to Kino Go TV!"

    tags = _dedupe_tags(BASE_TAGS + extra_tags)

    if existing_desc and len(existing_desc.strip()) > 80:
        description = existing_desc.strip()
        if "Kino Go TV" not in description:
            description += f"\n\n🎬 Kino Go TV — movie Shorts & cinema edits{lang_note}\n#shorts #movies #cinema #film"
    else:
        description = (
            f"{hook}\n\n"
            "🎬 Kino Go TV — movie Shorts, slowed edits & viral cinema moments.\n"
            "New film clips every day. Subscribe so you don't miss the next scene!"
            f"{lang_note}\n\n"
            "#shorts #movies #cinema #film #movieedits #filmedit #kino"
        )

    return {
        "description": description[:5000],
        "tags": tags,
        "categoryId": FILM_CATEGORY,
    }


CHANNEL_TITLE = "Kino Go TV"
CHANNEL_DESCRIPTION = """🎬 Kino Go TV — Movie Shorts & Cinema Edits

Daily viral film moments, slowed edits, and the best scenes from movies & series.
Action, Marvel, drama, Russian cinema highlights — all in vertical Shorts format.

🔥 New movie Shorts every day
📽️ Film edits | Movie quotes | Cinema clips
👇 Subscribe and turn on notifications

#movies #cinema #film #shorts #movieedits #filmedit #kino #movieclips
"""

CHANNEL_KEYWORDS = (
    "movie shorts, film edits, cinema shorts, movie clips, viral film moments, "
    "passenger 57, marvel edits, spider-man edit, venom edit, tom cruise, "
    "russian cinema, kino, фильм, сериал, movie quotes, slowed edit, hollywood shorts"
)

PLAYLISTS = [
    {
        "title": "🔥 Best Movie Edits",
        "description": "Top-performing cinema Shorts and viral movie moments on Kino Go TV.",
        "keywords": ["best movie edits", "viral film", "cinema shorts"],
        "match": ["passenger", "exactly", "великан", "снайпер", "bull", "venom"],
        "video_ids": ["CVDMMbSEyyk", "eXaIiYCdeMY", "atZV42Y95Tc", "tBpmKL5ne6Y"],
    },
    {
        "title": "Marvel & Superhero Edits",
        "description": "Marvel movie Shorts — Spider-Man, Venom, and superhero edits.",
        "keywords": ["marvel", "spider-man", "venom", "superhero"],
        "match": ["venom", "spider", "peter", "tony", "marvel"],
        "video_ids": ["KSsU_yK_yhs", "Rs56px0i6W8"],
    },
    {
        "title": "Russian Cinema Shorts",
        "description": "Лучшие кино-моменты и сериалы — Shorts на русском.",
        "keywords": ["кино", "фильм", "сериал", "русское кино"],
        "match": ["фильм", "сериал", "смогла", "медведь", "тюрьм", "миллион", "пророчеств", "великан"],
        "video_ids": [],
    },
    {
        "title": "Hollywood Action Moments",
        "description": "Hollywood action & drama movie clips in Shorts format.",
        "keywords": ["hollywood", "action movie", "tom cruise", "movie scene"],
        "match": ["tom cruise", "knight", "passenger", "bruce"],
        "video_ids": ["CVDMMbSEyyk", "tBpmKL5ne6Y"],
    },
]

SECTION_SPECS = [
    ("🔥 Best Movie Edits", 0),
    ("Marvel Edits", 1),
    ("Russian Cinema", 2),
]
