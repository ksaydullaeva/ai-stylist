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
    """Derive a balanced list of occasions from captioned item attributes.

    Always returns a diverse set so the model generates varied outfits rather
    than defaulting entirely to casual.  The anchor's style_category is kept as
    one entry; the remaining slots are filled from a fixed balanced pool so that
    at least one elevated occasion (smart-casual, business casual, or date night)
    is always present.
    """
    BALANCED_POOL = ["casual", "smart-casual", "business casual", "date night"]

    result: list[str] = []

    # Use the garment's own style_category as the first (most relevant) occasion.
    sc = attributes.get("style_category")
    if sc and isinstance(sc, str) and sc.strip():
        result.append(sc.strip().lower())

    # Fill remaining slots from the balanced pool, skipping duplicates.
    for occasion in BALANCED_POOL:
        if occasion not in result:
            result.append(occasion)
        if len(result) >= 4:
            break

    return result


def attach_image_urls(outfits: list, image_results: list) -> None:
    """Mutate each outfit item in-place, adding an `image_url` key from generated file paths."""
    for idx, outfit in enumerate(outfits):
        if idx >= len(image_results):
            break
        item_paths = image_results[idx].get("individual_items") or []
        for j, item in enumerate(outfit.get("items", [])):
            if j < len(item_paths) and item_paths[j]:
                item["image_url"] = f"/outputs/{Path(item_paths[j]).name}"
