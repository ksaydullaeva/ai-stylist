"""
Pipeline orchestration helpers shared by the HTTP API and the gRPC servicer.
"""

import threading
from functools import lru_cache
from pathlib import Path

from core.config import settings
from ai.image_generator import OutfitImageGenerator

UPLOAD_DIR: Path = settings.UPLOAD_DIR
OUTPUT_DIR: Path = settings.OUTPUT_DIR

_generator_lock = threading.Lock()


@lru_cache(maxsize=1)
def _create_image_generator() -> OutfitImageGenerator:
    """Single creation path; cached by lru_cache."""
    return OutfitImageGenerator()


def get_image_generator() -> OutfitImageGenerator:
    """Return a process-wide singleton image generator. Safe to call from multiple threads."""
    with _generator_lock:
        return _create_image_generator()


def occasions_from_attributes(attributes: dict) -> list[str]:
    """Derive a list of occasions from captioned item attributes (fallback when user leaves blank)."""
    result: list[str] = []
    if attributes.get("style_category"):
        sc = attributes["style_category"]
        result.append(sc if isinstance(sc, str) else str(sc))
    tags = attributes.get("tags")
    if isinstance(tags, list):
        for t in tags:
            if t and t not in result:
                result.append(t if isinstance(t, str) else str(t))
                if len(result) >= 3:
                    break
    return result or ["casual", "smart-casual"]


def attach_image_urls(outfits: list, image_results: list) -> None:
    """Mutate each outfit item in-place, adding an `image_url` key from generated file paths."""
    for idx, outfit in enumerate(outfits):
        if idx >= len(image_results):
            break
        item_paths = image_results[idx].get("individual_items") or []
        for j, item in enumerate(outfit.get("items", [])):
            if j < len(item_paths) and item_paths[j]:
                item["image_url"] = f"/outputs/{Path(item_paths[j]).name}"
