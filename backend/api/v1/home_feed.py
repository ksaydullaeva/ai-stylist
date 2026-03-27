"""
Home screen trend feed: static JSON only (`data/home_feed.json`).

Refresh occasionally with `python3 scripts/fetch_home_feed_rss.py` (public RSS feeds;
bundled in-repo; no runtime scraping).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from core.home_feed_modesty import filter_home_feed_payload

router = APIRouter(tags=["home"])

_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "home_feed.json"


@router.get("/home-trend-feed")
def home_trend_feed():
    """Returns { trending, spotlight, source } from bundled static data."""
    if not _DATA_PATH.is_file():
        return {"trending": [], "spotlight": [], "source": "empty"}
    with open(_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data = filter_home_feed_payload(data)
    data["source"] = "static"
    return data
