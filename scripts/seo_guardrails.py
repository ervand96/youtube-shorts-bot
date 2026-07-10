#!/usr/bin/env python3
"""SEO / policy guardrails for kids Shorts metadata."""

from __future__ import annotations

import re

# Brand impersonation / competitor names that trigger limited or spammy distribution.
BANNED_TAG_PATTERNS = [
    re.compile(r"cocomelon", re.I),
    re.compile(r"pinkfong", re.I),
    re.compile(r"little\s*baby\s*bum", re.I),
    re.compile(r"super\s*simple\s*songs", re.I),
    re.compile(r"ms\s*rachel", re.I),
]

# High copyright-risk titles/topics that often get muted, claimed, or buried.
COPYRIGHT_RISK_PATTERNS = [
    re.compile(r"baby\s*shark", re.I),
    re.compile(r"let\s*it\s*go", re.I),
    re.compile(r"frozen", re.I),
    re.compile(r"pep\s*pa\s*pig", re.I),
    re.compile(r"paw\s*patrol", re.I),
]


def sanitize_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags or []:
        text = " ".join(str(tag).split()).strip()
        if not text:
            continue
        if any(p.search(text) for p in BANNED_TAG_PATTERNS):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text[:30])
    return cleaned[:15]


def copyright_risk_hits(text: str) -> list[str]:
    hits = []
    for pattern in COPYRIGHT_RISK_PATTERNS:
        if pattern.search(text or ""):
            hits.append(pattern.pattern)
    return hits


def assert_safe_metadata(metadata: dict) -> None:
    blob = " ".join(
        [
            str(metadata.get("title", "")),
            str(metadata.get("description", "")),
            " ".join(metadata.get("tags") or []),
        ]
    )
    hits = copyright_risk_hits(blob)
    if hits:
        raise ValueError(
            "Metadata looks like high copyright-risk kids IP "
            f"({', '.join(hits)}). Use original Benny songs/stories instead."
        )
    metadata["tags"] = sanitize_tags(metadata.get("tags"))
