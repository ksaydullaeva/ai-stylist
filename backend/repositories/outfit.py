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
) -> list[int]:
    """Persist outfits and their individual items to the database. Returns list of created outfit IDs."""
    session = SessionLocal()
    outfit_ids: list[int] = []
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
            outfit_ids.append(db_outfit.id)

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
        outfit_ids = []
    finally:
        session.close()
    return outfit_ids


def persist_single_outfit(
    outfit: dict,
    image_result: dict,
    source_filepath: Path,
    attributes: dict,
    try_on_filename: str | None = None,
) -> int | None:
    """Persist one outfit and its items. Returns created outfit ID or None on failure.
    try_on_filename: optional filename of try-on image (e.g. tryon_abc123.jpg) if already generated."""
    session = SessionLocal()
    try:
        db_outfit = Outfit(
            occasion=outfit.get("occasion", ""),
            style_title=outfit.get("style_title", ""),
            style_notes=outfit.get("style_notes", ""),
            color_palette=outfit.get("color_palette") or [],
            source_image_path=str(source_filepath),
            attributes=attributes,
            try_on_image_path=try_on_filename,
        )
        session.add(db_outfit)
        session.flush()
        outfit_id = db_outfit.id
        item_paths = image_result.get("individual_items") or []
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
        return outfit_id
    except Exception as exc:
        session.rollback()
        logger.warning("Could not persist single outfit: %s", exc)
        return None
    finally:
        session.close()


def update_outfit_try_on(outfit_id: int, try_on_filename: str) -> bool:
    """Set try_on_image_path for an outfit. Returns True if updated."""
    session = SessionLocal()
    try:
        row = session.query(Outfit).filter(Outfit.id == outfit_id).first()
        if not row:
            return False
        row.try_on_image_path = try_on_filename
        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        logger.warning("Could not update outfit try-on: %s", exc)
        return False
    finally:
        session.close()


def list_outfits(limit: int = 50) -> list[dict]:
    """List saved outfits for later reference (most recent first)."""
    session = SessionLocal()
    try:
        rows = (
            session.query(Outfit)
            .order_by(Outfit.created_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for o in rows:
            items = [
                {
                    "id": i.id,
                    "category": i.category,
                    "color": i.color,
                    "type": i.type,
                    "description": i.description,
                    "shopping_keywords": i.shopping_keywords,
                    "image_url": f"/outputs/{Path(i.image_path).name}" if i.image_path else None,
                }
                for i in sorted(o.items, key=lambda x: x.id)
            ]
            result.append({
                "id": o.id,
                "occasion": o.occasion,
                "style_title": o.style_title,
                "style_notes": o.style_notes,
                "color_palette": o.color_palette or [],
                "attributes": o.attributes or {},
                "source_image_url": (
                    f"/uploads/{Path(o.source_image_path).name}" if "uploads" in o.source_image_path else
                    f"/outputs/{Path(o.source_image_path).name}" if "outputs" in o.source_image_path else
                    f"/outputs/{Path(o.source_image_path).name}"  # fallback
                ) if o.source_image_path else None,
                "try_on_image_url": f"/outputs/{o.try_on_image_path}" if o.try_on_image_path else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "items": items,
            })
        return result
    finally:
        session.close()
def delete_outfit(outfit_id: int) -> bool:
    """Delete an outfit and its items from the database. Returns True if deleted."""
    session = SessionLocal()
    try:
        row = session.query(Outfit).filter(Outfit.id == outfit_id).first()
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        logger.warning("Could not delete outfit: %s", exc)
        return False
    finally:
        session.close()

def delete_all_outfits() -> bool:
    """Wipe all saved outfits and their items."""
    session = SessionLocal()
    try:
        from sqlalchemy import text
        # Clean up any potential ghost tables or items first
        session.execute(text("DELETE FROM outfit_items"))
        session.execute(text("DELETE FROM outfit_images")) # Ghost table causing FK violation
        session.execute(text("DELETE FROM outfits"))
        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        raise exc
    finally:
        session.close()
