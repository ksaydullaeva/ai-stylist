"""Data access layer for outfit persistence."""

import logging
from pathlib import Path

from core.database import SessionLocal
from models.orm import Outfit, OutfitItem

logger = logging.getLogger(__name__)


def persist_outfits(
    outfits: list,
    image_results: list,
    source_filepath: Path,
    attributes: dict,
) -> None:
    """Persist outfits and their individual items to the database."""
    session = SessionLocal()
    try:
        for idx, outfit in enumerate(outfits):
            db_outfit = Outfit(
                occasion=outfit.get("occasion", ""),
                style_title=outfit.get("style_title", ""),
                style_notes=outfit.get("style_notes", ""),
                color_palette=outfit.get("color_palette") or [],
                source_image_path=str(source_filepath),
                attributes=attributes,
            )
            session.add(db_outfit)
            session.flush()

            item_paths = (
                image_results[idx].get("individual_items") or []
                if idx < len(image_results)
                else []
            )
            for j, item in enumerate(outfit.get("items", [])):
                session.add(
                    OutfitItem(
                        outfit_id=db_outfit.id,
                        category=item.get("category"),
                        color=item.get("color"),
                        type=item.get("type"),
                        description=item.get("description"),
                        shopping_keywords=item.get("shopping_keywords"),
                        image_path=item_paths[j] if j < len(item_paths) else None,
                    )
                )
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Could not persist outfits to database: %s", exc)
    finally:
        session.close()
