#!/usr/bin/env python3
"""Deep channel diagnosis for zero-view / low-reach Shorts.

Pulls live YouTube Data API state, scores risk factors, and writes
analytics/channel-diagnosis-live.json for review.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.seo_guardrails import BANNED_TAG_PATTERNS, copyright_risk_hits, sanitize_tags
from scripts.youtube_client import get_youtube_service

OUT_PATH = ROOT / "analytics" / "channel-diagnosis-live.json"


def diagnosis_out_path(channel: str) -> Path:
    if channel in {"benny", "kids", "default"}:
        return OUT_PATH
    safe = channel.replace(" ", "-").lower()
    return ROOT / "analytics" / f"channel-diagnosis-{safe}.json"


def list_all_uploads(youtube) -> list[str]:
    ch = youtube.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids: list[str] = []
    token = None
    while True:
        kwargs = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if token:
            kwargs["pageToken"] = token
        page = youtube.playlistItems().list(**kwargs).execute()
        ids.extend(item["contentDetails"]["videoId"] for item in page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            break
    return ids


def fetch_videos(youtube, video_ids: list[str]) -> list[dict]:
    rows: list[dict] = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = (
            youtube.videos()
            .list(part="snippet,status,statistics,contentDetails", id=",".join(batch))
            .execute()
        )
        for v in resp.get("items", []):
            tags = v["snippet"].get("tags") or []
            title = v["snippet"]["title"]
            desc = v["snippet"].get("description") or ""
            banned = [t for t in tags if any(p.search(t) for p in BANNED_TAG_PATTERNS)]
            risk = copyright_risk_hits(f"{title} {desc} {' '.join(tags)}")
            rows.append(
                {
                    "id": v["id"],
                    "url": f"https://youtube.com/shorts/{v['id']}",
                    "title": title,
                    "description": desc,
                    "published": v["snippet"]["publishedAt"],
                    "views": int(v["statistics"].get("viewCount", 0)),
                    "likes": int(v["statistics"].get("likeCount", 0)),
                    "comments": int(v["statistics"].get("commentCount", 0)),
                    "duration": v["contentDetails"]["duration"],
                    "privacy": v["status"]["privacyStatus"],
                    "uploadStatus": v["status"].get("uploadStatus"),
                    "madeForKids": v["status"].get("madeForKids"),
                    "selfDeclaredMadeForKids": v["status"].get("selfDeclaredMadeForKids"),
                    "categoryId": v["snippet"].get("categoryId"),
                    "tags": tags,
                    "banned_tags": banned,
                    "copyright_risk": risk,
                    "issues": [],
                }
            )
    rows.sort(key=lambda r: r["published"])
    return rows


def score_video(row: dict, burst_ids: set[str]) -> None:
    issues: list[str] = []
    if row["views"] == 0:
        issues.append("zero_views")
    if row["banned_tags"]:
        issues.append("brand_impersonation_tags")
    if row["copyright_risk"]:
        issues.append("copyright_risk_ip")
    if row["id"] in burst_ids:
        issues.append("burst_publish_same_minute")
    if row["privacy"] != "public":
        issues.append(f"privacy_{row['privacy']}")
    if row["uploadStatus"] != "processed":
        issues.append(f"upload_{row['uploadStatus']}")
    row["issues"] = issues


def detect_burst_publishes(rows: list[dict], window_seconds: int = 120) -> set[str]:
    """Videos published within window_seconds of another upload (spam signal)."""
    burst: set[str] = set()
    parsed = []
    for row in rows:
        ts = datetime.fromisoformat(row["published"].replace("Z", "+00:00"))
        parsed.append((ts, row["id"]))
    for i, (ts_i, id_i) in enumerate(parsed):
        for ts_j, id_j in parsed[i + 1 :]:
            if abs((ts_j - ts_i).total_seconds()) <= window_seconds:
                burst.add(id_i)
                burst.add(id_j)
            else:
                break
    return burst


def build_findings(channel: dict, rows: list[dict]) -> list[dict]:
    total_views = sum(r["views"] for r in rows)
    zero = sum(1 for r in rows if r["views"] == 0)
    banned = sum(1 for r in rows if r["banned_tags"])
    copyrighted = sum(1 for r in rows if r["copyright_risk"])
    burst = sum(1 for r in rows if "burst_publish_same_minute" in r["issues"])
    avg_views = (total_views / len(rows)) if rows else 0

    findings = []
    if zero >= max(1, len(rows) // 2) or avg_views < 5:
        findings.append(
            {
                "severity": "critical",
                "code": "cold_start_no_impressions",
                "title": "Almost no distribution yet",
                "detail": (
                    f"Channel has {channel['videoCount']} videos but only {channel['views']} "
                    f"channel views ({total_views} summed on videos). {zero}/{len(rows)} Shorts "
                    "still sit at 0 views — YouTube is barely testing them in the Shorts feed."
                ),
            }
        )

    if channel.get("madeForKids") or channel.get("selfDeclaredMadeForKids"):
        findings.append(
            {
                "severity": "critical",
                "code": "made_for_kids_limits_shorts_feed",
                "title": "Made for Kids limits Shorts feed reach",
                "detail": (
                    "Channel and videos are Made for Kids (required for kids niches under COPPA). "
                    "MFK disables comments/notifications and blocks personalized Shorts targeting, "
                    "so growth is much slower than general-audience Shorts. Do NOT flip this off for "
                    "kids content. Expect search + parent shares + YouTube Kids, not viral Shorts."
                ),
            }
        )

    if banned:
        findings.append(
            {
                "severity": "high",
                "code": "brand_impersonation_tags",
                "title": f"{banned} videos use competitor brand tags",
                "detail": (
                    "Tags like 'cocomelon style' look like brand impersonation and can suppress "
                    "recommendations. Strip them from live videos and stop adding them on upload."
                ),
            }
        )
    if copyrighted:
        findings.append(
            {
                "severity": "high",
                "code": "copyright_risk_ip",
                "title": f"{copyrighted} videos reference high-risk kids IP",
                "detail": (
                    "Titles/tags like Baby Shark are frequently claimed or limited. "
                    "Prefer original Benny songs and public-domain nursery rhymes with original arrangements."
                ),
            }
        )
    if burst:
        findings.append(
            {
                "severity": "high",
                "code": "burst_publish",
                "title": f"{burst} videos published in the same minute",
                "detail": (
                    "Dumping multiple Shorts within seconds looks like spam to the algorithm. "
                    "Always use staggered --publish-at scheduling (already in run_daily_batch.py)."
                ),
            }
        )
    if channel["subs"] <= 1:
        findings.append(
            {
                "severity": "medium",
                "code": "no_seed_audience",
                "title": "No seed audience (1 subscriber)",
                "detail": (
                    "New/reactivated channels need a few real watches from parents/friends "
                    "in the first hours. Without that seed, MFK Shorts often stay at 0–2 views."
                ),
            }
        )

    return findings


def sanitize_live_videos(youtube, rows: list[dict], dry_run: bool = False) -> list[dict]:
    """Remove banned tags from live videos; keep title/description/category/status intact."""
    actions = []
    for row in rows:
        if not row["banned_tags"]:
            continue
        clean_tags = sanitize_tags(row["tags"])
        action = {
            "id": row["id"],
            "title": row["title"],
            "removed_tags": row["banned_tags"],
            "new_tags": clean_tags,
            "status": "dry_run" if dry_run else "pending",
        }
        if dry_run:
            actions.append(action)
            continue
        # videos.update replaces mutable snippet fields — must resend required ones.
        body = {
            "id": row["id"],
            "snippet": {
                "title": row["title"],
                "description": row.get("description") or "",
                "categoryId": row["categoryId"] or "24",
                "tags": clean_tags,
            },
        }
        youtube.videos().update(part="snippet", body=body).execute()
        action["status"] = "updated"
        actions.append(action)
        print(f"Sanitized tags: {row['id']} removed={row['banned_tags']}")
    return actions


def unpublish_copyright_risk(youtube, rows: list[dict], dry_run: bool = False) -> list[dict]:
    """Set high copyright-risk videos to private so they stop hurting the channel."""
    actions = []
    for row in rows:
        if not row["copyright_risk"] or row["privacy"] != "public":
            continue
        action = {
            "id": row["id"],
            "title": row["title"],
            "risk": row["copyright_risk"],
            "status": "dry_run" if dry_run else "pending",
        }
        if dry_run:
            actions.append(action)
            continue
        body = {
            "id": row["id"],
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": True,
            },
        }
        youtube.videos().update(part="status", body=body).execute()
        action["status"] = "set_private"
        actions.append(action)
        print(f"Unpublished copyright-risk: {row['id']} {row['title']}")
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose YouTube channel reach problems")
    parser.add_argument(
        "--channel",
        default="benny",
        help="OAuth profile: benny (kids) or kinogo (Kino Go TV)",
    )
    parser.add_argument(
        "--fix-tags",
        action="store_true",
        help="Remove banned brand tags from live videos",
    )
    parser.add_argument(
        "--unpublish-risky",
        action="store_true",
        help="Set copyright-risk videos (e.g. Baby Shark) to private",
    )
    parser.add_argument("--dry-run", action="store_true", help="With fix flags, only print")
    args = parser.parse_args()

    youtube = get_youtube_service(args.channel)
    ch = youtube.channels().list(part="snippet,statistics,status", mine=True).execute()["items"][0]
    channel = {
        "id": ch["id"],
        "title": ch["snippet"]["title"],
        "customUrl": ch["snippet"].get("customUrl"),
        "views": int(ch["statistics"]["viewCount"]),
        "subs": int(ch["statistics"]["subscriberCount"]),
        "videoCount": int(ch["statistics"]["videoCount"]),
        "madeForKids": ch["status"].get("madeForKids"),
        "selfDeclaredMadeForKids": ch["status"].get("selfDeclaredMadeForKids"),
        "publishedAt": ch["snippet"]["publishedAt"],
        "url": f"https://youtube.com/{ch['snippet'].get('customUrl') or ('channel/' + ch['id'])}",
    }

    video_ids = list_all_uploads(youtube)
    rows = fetch_videos(youtube, video_ids)
    burst_ids = detect_burst_publishes(rows)
    for row in rows:
        score_video(row, burst_ids)

    findings = build_findings(channel, rows)
    actions: list[dict] = []
    if args.fix_tags:
        actions.extend(sanitize_live_videos(youtube, rows, dry_run=args.dry_run))
    if args.unpublish_risky:
        actions.extend(unpublish_copyright_risk(youtube, rows, dry_run=args.dry_run))
    if not args.dry_run and actions:
        rows = fetch_videos(youtube, video_ids)
        for row in rows:
            score_video(row, burst_ids)

    out_path = diagnosis_out_path(args.channel)
    report = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.channel,
        "channel": channel,
        "summary": {
            "videos": len(rows),
            "total_views": sum(r["views"] for r in rows),
            "zero_view_videos": sum(1 for r in rows if r["views"] == 0),
            "banned_tag_videos": sum(1 for r in rows if r["banned_tags"]),
            "copyright_risk_videos": sum(1 for r in rows if r["copyright_risk"]),
            "burst_publish_videos": len(burst_ids),
        },
        "findings": findings,
        "fix_actions": actions,
        "videos": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"profile": args.channel, "summary": report["summary"], "findings": findings, "fix_actions": actions}, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
