#!/usr/bin/env python3
"""
One-time (or occasional) refresh of the home trend feed from public RSS feeds.

Uses syndication URLs publishers expose for aggregators — not HTML scraping.
Run manually when you want fresher headlines/images:

  python3 scripts/fetch_home_feed_rss.py

Writes:
  - backend/data/home_feed.json
  - web/src/data/homeFeed.json (same content, for offline frontend fallback)

Respect each site’s terms and robots.txt; do not hammer feeds or re-run in production.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
from core.home_feed_modesty import filter_home_feed_payload, item_excluded_modesty_uz  # noqa: E402

OUT_BACKEND = REPO / "backend" / "data" / "home_feed.json"
OUT_WEB = REPO / "web" / "src" / "data" / "homeFeed.json"

# Public RSS endpoints (syndication; check publisher terms before redistributing).
FEEDS: list[tuple[str, str]] = [
    ("Vogue", "https://www.vogue.com/feed/rss"),
    ("ELLE", "https://www.elle.com/rss/all.xml"),
    ("Harper's Bazaar", "https://www.harpersbazaar.com/rss/all.xml"),
    ("Who What Wear", "https://www.whowhatwear.com/rss"),
    ("Glamour", "https://www.glamour.com/feed/rss"),
]

USER_AGENT = (
    "StylistOutfitSuggestion/1.0 (+https://example.local; home feed RSS refresh; contact: dev)"
)

IMG_IN_HTML = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

# Fallback hero images if a feed item has no media (HTTPS only).
STOCK_IMAGES = [
    "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=900&q=82",
    "https://images.unsplash.com/photo-1539008835657-9e8f37604c4f?auto=format&fit=crop&w=900&q=82",
    "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?auto=format&fit=crop&w=900&q=82",
    "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?auto=format&fit=crop&w=900&q=82",
    "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=900&q=82",
    "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=82",
    "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=82",
]

TRENDING_GRADIENTS = [
    "linear-gradient(145deg, #fffbeb 0%, #fde68a 45%, #e7e5e4 100%)",
    "linear-gradient(160deg, #f8fafc 0%, #cbd5e1 55%, #94a3b8 100%)",
    "linear-gradient(135deg, #faf5f0 0%, #d6c4b8 50%, #a89084 100%)",
    "linear-gradient(145deg, #fdf4ff 0%, #e9d5ff 40%, #c4b5fd 100%)",
]

SPOTLIGHT_GRADIENTS = [
    "linear-gradient(180deg, rgba(180,116,86,0.12) 0%, rgba(26,26,26,0.06) 100%)",
    "linear-gradient(180deg, rgba(59,47,42,0.1) 0%, rgba(248,249,250,0.9) 100%)",
    "linear-gradient(165deg, #fff7ed 0%, #fed7aa 55%, #fb923c 100%)",
]

SPOTLIGHT_ACCENTS = ["#b47456", "#3b2f2a", "#7c2d12"]

# Trending rail: topic-led (styles, products, beauty, hair) — not celebrity gossip / premieres.
_TREND_TERMS = (
    "makeup",
    "beauty",
    "hair",
    "hairstyle",
    "skin",
    "nail",
    "trend",
    "street style",
    "runway",
    "styling",
    "how to style",
    "outfit",
    "dress",
    "skirt",
    "denim",
    "boot",
    "sneaker",
    "shoe",
    "bag",
    "jewelry",
    "collection",
    "shop",
    "fall 20",
    "spring 20",
    "summer 20",
    "color",
    "palette",
    "lookbook",
    "capsule",
)


def _blob(row: dict) -> str:
    t = (row.get("title") or "").lower()
    link = (row.get("link") or "").lower()
    d = (row.get("detail") or row.get("summary") or "").lower()
    cats = " ".join(row.get("categories") or []).lower()
    return f"{t} {link} {d} {cats}"


def is_excluded_from_trending(row: dict) -> bool:
    """Celebrity-led or off-topic stories we skip for the Trending rail."""
    b = _blob(row)
    link = (row.get("link") or "").lower()
    title = (row.get("title") or "").lower()

    if "relationship timeline" in b or "complete relationship" in b:
        return True
    if "/celebrities/" in link or "/culture/celebrities/" in link:
        return True
    # Red-carpet / who-wore-what (e.g. Zendaya premiere)
    if re.search(r"\b(wears|wore)\b.+\b(dress|gown|suit)\b", title):
        return True
    if "premiere" in title and re.search(r"\b(wears|wore|borrowed)\b", title):
        return True
    if re.search(r"\b(?:at the|movie|film)\s+premiere\b", title):
        return True
    # “Star’s favorite bag”–style pieces — keep spotlight, skip for topic-led trending
    if re.search(r"['\u2019]s\s+favorite\b", title, re.I):
        return True
    if re.search(r"\btracked\s+down\b.+\b(headband|bag|dress|ring)\b", title, re.I):
        return True
    tag = (row.get("tag") or "").lower()
    if "celebrity" in tag and "style" not in tag and "beauty" not in tag:
        return True
    return False


def trend_score(row: dict) -> int:
    """Higher = more clearly about a look, product, or beauty trend."""
    b = _blob(row)
    s = 0
    for term in _TREND_TERMS:
        if term in b:
            s += 2
    tag = (row.get("tag") or "").lower()
    if any(x in tag for x in ("beauty", "makeup", "hair", "runway", "shopping", "style")):
        s += 1
    if "celebrity" in tag:
        s -= 4
    if "culture" in tag and "tv" in tag:
        s -= 3
    return s


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def _strip_tags(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", " ", text)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _first_img_from_html(html_blob: str) -> str | None:
    if not html_blob:
        return None
    m = IMG_IN_HTML.search(html_blob)
    return m.group(1) if m else None


def _parse_pub_date(el: ET.Element) -> datetime | None:
    for child in el:
        local = child.tag.split("}")[-1]
        if local not in ("pubDate", "published", "updated"):
            continue
        raw = (child.text or "").strip()
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def _item_image(item: ET.Element, ns: dict[str, str]) -> str | None:
    media_ns = ns.get("media", "http://search.yahoo.com/mrss/")
    # media:thumbnail url="..."
    for thumb in item.findall(f".//{{{media_ns}}}thumbnail"):
        u = thumb.get("url")
        if u and u.startswith("https://"):
            return u
    # media:content url="..."
    for mc in item.findall(f".//{{{media_ns}}}content"):
        u = mc.get("url")
        if u and u.startswith("https://"):
            return u
    # enclosure
    for enc in item.findall("enclosure"):
        u = enc.get("url") or enc.get("href")
        if u and u.startswith("https://") and (enc.get("type") or "").startswith("image"):
            return u
    # description / content:encoded
    for child in item:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in ("description", "content"):
            blob = child.text or ""
            u = _first_img_from_html(blob)
            if u and u.startswith("https://"):
                return u
    return None


def _item_categories(item: ET.Element) -> list[str]:
    out: list[str] = []
    for child in item:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "category" and child.text:
            out.append(_strip_tags(child.text))
    return [c for c in out if c]


def _item_fields(item: ET.Element, is_atom: bool) -> dict[str, str | None]:
    title = link = desc = None
    if is_atom:
        for child in item:
            local = child.tag.split("}")[-1]
            if local == "title" and child.text:
                title = _strip_tags(child.text)
            elif local == "link" and child.get("href"):
                link = child.get("href")
            elif local in ("summary", "content"):
                inner = "".join(child.itertext()) if list(child) else (child.text or "")
                desc = inner
    else:
        for child in item:
            local = child.tag.split("}")[-1]
            if local == "title" and (child.text or "").strip():
                title = _strip_tags(child.text or "")
            elif local == "link" and (child.text or "").strip():
                link = (child.text or "").strip()
            elif local == "description" and (child.text or "").strip():
                desc = child.text
    return {"title": title, "link": link, "description": desc}


def parse_feed(xml_bytes: bytes, source_name: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    ns = {}
    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0][1:]
        if "atom" in uri.lower() or "2005" in uri:
            ns["atom"] = uri

    channel = root.find("channel")
    if channel is not None:
        items = channel.findall("item")
        is_atom = False
        wrap = channel
    else:
        # Atom: entries at top level
        items = root.findall("{http://www.w3.org/2005/Atom}entry")
        if not items:
            items = [e for e in root if e.tag.endswith("entry")]
        is_atom = True
        wrap = root

    # Collect namespace URIs from document
    for ev in root.iter():
        if ev.tag.startswith("{"):
            uri = ev.tag[1:].split("}")[0]
            if "media" in uri:
                ns["media"] = uri

    out: list[dict] = []
    for item in items:
        fields = _item_fields(item, is_atom)
        title = fields.get("title")
        link = fields.get("link")
        if not title or not link:
            continue
        desc_raw = fields.get("description") or ""
        plain = _strip_tags(desc_raw) if desc_raw else ""
        pub = _parse_pub_date(item)
        image = _item_image(item, ns)
        cats = _item_categories(item)
        tag = "Style"
        if cats:
            tag = cats[0].split("/")[-1].strip()[:32] or "Style"
        out.append(
            {
                "title": title[:200],
                "link": link,
                "summary": (plain[:280] + "…") if len(plain) > 280 else plain,
                "detail": plain,
                "imageUrl": image,
                "pub": pub,
                "tag": tag,
                "source": source_name,
                "categories": cats,
            }
        )
    return out


def _dedupe_newest_first(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for r in sorted(
        rows,
        key=lambda x: x["pub"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    ):
        link = r["link"]
        if link in seen:
            continue
        seen.add(link)
        unique.append(r)
    return unique


def _round_robin_pick(pool: list[dict], n: int, *, sort_key) -> list[dict]:
    """Take n items, round-robin by publisher; each publisher queue ordered by sort_key."""
    if not pool or n <= 0:
        return []
    by_source: dict[str, list[dict]] = {}
    for r in pool:
        by_source.setdefault(r.get("source") or "unknown", []).append(r)
    for src in by_source:
        by_source[src].sort(key=sort_key, reverse=True)
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    sources = sorted(
        by_source.keys(),
        key=lambda s: (by_source[s][0].get("pub") or _epoch),
        reverse=True,
    )
    picked: list[dict] = []
    rnd = 0
    while len(picked) < n and any(by_source.get(s) for s in sources):
        for s in sources:
            if len(picked) >= n:
                break
            lst = by_source.get(s) or []
            if lst:
                picked.append(lst.pop(0))
        rnd += 1
        if rnd > 200:
            break
    return picked


def merge_and_pick(rows: list[dict]) -> list[dict]:
    """Four trend-topic stories for trending + three for spotlight (diverse sources)."""
    rows = [r for r in rows if not item_excluded_modesty_uz(r)]
    unique = _dedupe_newest_first(rows)
    _epoch = datetime.min.replace(tzinfo=timezone.utc)

    def _pub_key(r: dict):
        return r.get("pub") or _epoch

    trend_pool = [r for r in unique if not is_excluded_from_trending(r)]
    # Prefer higher trend_score, then recency
    trend_pool.sort(key=lambda r: (trend_score(r), _pub_key(r)), reverse=True)

    trending = _round_robin_pick(
        trend_pool,
        4,
        sort_key=lambda r: (trend_score(r), _pub_key(r)),
    )
    if len(trending) < 4:
        need = 4 - len(trending)
        used = {r["link"] for r in trending}
        filler = [r for r in trend_pool if r["link"] not in used][:need]
        if len(filler) < need:
            rest = [
                r
                for r in unique
                if r["link"] not in used and r["link"] not in {x["link"] for x in filler}
                and not is_excluded_from_trending(r)
            ]
            filler.extend(rest[: need - len(filler)])
        if len(filler) < need:
            blocked = used | {x["link"] for x in filler}
            rest2 = [r for r in unique if r["link"] not in blocked][: need - len(filler)]
            filler.extend(rest2)
        trending.extend(filler[:need])

    used_links = {r["link"] for r in trending}
    spotlight_pool = [r for r in unique if r["link"] not in used_links]
    spotlight_pool.sort(key=_pub_key, reverse=True)
    spotlight = _round_robin_pick(
        spotlight_pool,
        3,
        sort_key=_pub_key,
    )
    if len(spotlight) < 3:
        need = 3 - len(spotlight)
        u2 = used_links | {r["link"] for r in spotlight}
        more = [r for r in unique if r["link"] not in u2][:need]
        spotlight.extend(more)

    return trending[:4] + spotlight[:3]


def _with_source_note(detail: str, summary: str, source: str | None) -> str:
    if not source:
        return (detail or summary or "").strip()
    base = (detail or summary or "").strip()
    if len(base) >= 400:
        return base
    note = f"Originally summarized from {source}'s RSS feed."
    if not base:
        return note
    sep = "" if base.endswith((".", "!", "?", "…")) else "."
    return f"{base}{sep} {note}"


def build_payload(rows: list[dict]) -> dict:
    trending: list[dict] = []
    spotlight: list[dict] = []
    for i, r in enumerate(rows[:4]):
        img = r["imageUrl"] or STOCK_IMAGES[i % len(STOCK_IMAGES)]
        detail = _with_source_note(str(r.get("detail") or ""), str(r.get("summary") or ""), r.get("source"))
        trending.append(
            {
                "id": f"t{i + 1}",
                "tag": r["tag"],
                "title": r["title"],
                "summary": r["summary"] or r["title"][:160],
                "detail": detail.strip(),
                "imageUrl": img,
                "imageAlt": r["title"][:120],
                "gradient": TRENDING_GRADIENTS[i % len(TRENDING_GRADIENTS)],
            }
        )
    for j, r in enumerate(rows[4:7]):
        img = r["imageUrl"] or STOCK_IMAGES[(j + 4) % len(STOCK_IMAGES)]
        detail = _with_source_note(str(r.get("detail") or ""), str(r.get("summary") or ""), r.get("source"))
        spotlight.append(
            {
                "id": f"s{j + 1}",
                "tag": r["tag"],
                "title": r["title"],
                "summary": r["summary"] or r["title"][:160],
                "detail": detail.strip(),
                "imageUrl": img,
                "imageAlt": r["title"][:120],
                "accent": SPOTLIGHT_ACCENTS[j % len(SPOTLIGHT_ACCENTS)],
                "gradient": SPOTLIGHT_GRADIENTS[j % len(SPOTLIGHT_GRADIENTS)],
            }
        )
    return {"trending": trending, "spotlight": spotlight}


def main() -> int:
    all_rows: list[dict] = []
    for name, url in FEEDS:
        try:
            raw = _fetch(url)
            all_rows.extend(parse_feed(raw, name))
        except Exception as e:
            print(f"WARN: {name} ({url}): {e}", file=sys.stderr)

    if len(all_rows) < 7:
        print("ERROR: Not enough items from feeds. Check network and feed URLs.", file=sys.stderr)
        return 1

    picked = merge_and_pick(all_rows)
    payload = filter_home_feed_payload(build_payload(picked))

    OUT_BACKEND.parent.mkdir(parents=True, exist_ok=True)
    OUT_WEB.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUT_BACKEND.write_text(text, encoding="utf-8")
    OUT_WEB.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT_BACKEND} and {OUT_WEB} ({len(picked)} stories).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
