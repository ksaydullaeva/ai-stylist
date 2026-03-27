"""
Filter home-feed items for conservative dress norms (e.g. Uzbekistan market).

Excludes sheer / see-through / lingerie-led trends and similar editorial framing.
Used by the API when serving `home_feed.json` and by `scripts/fetch_home_feed_rss.py`.
"""

from __future__ import annotations

import re

# Title/summary/detail/alt text — avoid false positives like "see now, buy now"
_SHEER = re.compile(
    r"(?:\bsee-through\b|\bsee through\b|"
    r"\bsheer\s+(?:knit|dress|top|gown|look|trend|fabric|layer|shirt|skirt)|"
    r"\b(?:mesh|transparent|diaphanous)\s+(?:knit|dress|top|gown|look|trend)|"
    r"\b(?:naked|nude)\s+dress\b|"
    r"\blingerie\s+(?:trend|look)|"
    r"\bunderwear\s+as\s+outerwear|"
    r"\bno-?pants\s+(?:trend|look)|"
    r"\bbarely\s+there\s+(?:trend|look)|"
    r"\bbikini\b|\bthong\b|\bcleavage\b)",
    re.I,
)

_BATHHOUSE_SHOW = re.compile(
    r"\bbathhouse\b.+(?:show|runway|collection|fashion|spring|fall)",
    re.I,
)

_AMERICAN_GIGOLO = re.compile(r"american\s+gigolo", re.I)


def item_excluded_modesty_uz(item: dict) -> bool:
    """True if this card should not be shown (sheer/revealing editorial or similar)."""
    title = (item.get("title") or "").lower()
    blob = " ".join(
        [
            item.get("title") or "",
            item.get("summary") or "",
            item.get("detail") or "",
            item.get("imageAlt") or "",
        ]
    ).lower()

    if _AMERICAN_GIGOLO.search(title):
        return True
    if _BATHHOUSE_SHOW.search(title) or ("bathhouse" in title and "show" in title):
        return True
    if _SHEER.search(blob):
        return True
    return False


def filter_home_feed_payload(data: dict) -> dict:
    """Return a copy with trending/spotlight lists stripped of modesty exclusions."""
    out = dict(data)
    for key in ("trending", "spotlight"):
        if key not in out or not isinstance(out[key], list):
            continue
        out[key] = [x for x in out[key] if isinstance(x, dict) and not item_excluded_modesty_uz(x)]
    return out
