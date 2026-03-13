from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai.suggestion import generate_outfit_suggestions
from models.schemas import OutfitRequest
from repositories.outfit import list_outfits, delete_outfit, delete_all_outfits, persist_single_outfit
from services.pipeline import OUTPUT_DIR, UPLOAD_DIR

router = APIRouter(tags=["outfits"])


def _url_to_path(url: str, base: Path) -> Path | None:
    """Convert a URL like /outputs/foo.jpg to base/foo.jpg. Returns None if not under base."""
    if not url:
        return None
    name = Path(url).name
    if not name:
        return None
    return base / name


@router.post("/outfit-suggestions")
def get_outfit_suggestions(req: OutfitRequest):
    """Generate outfit suggestions from pre-extracted item attributes."""
    try:
        result = generate_outfit_suggestions(
            item_attributes=req.item_attributes,
            occasions=req.occasions,
        )
        return {"success": True, "outfits": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outfits")
def save_outfit(body: dict):
    """Save a single look for later reference. Body: outfit, image_result (flat_lay, individual_items URLs), image_id, attributes, optional try_on_url (/outputs/xxx)."""
    try:
        outfit = body.get("outfit")
        image_result = body.get("image_result") or {}
        image_id = body.get("image_id")
        attributes = body.get("attributes") or {}
        try_on_url = body.get("try_on_url") or ""
        if not outfit or not image_id:
            raise HTTPException(status_code=400, detail="outfit and image_id required")
        # Resolve image_id (/uploads/xxx or /outputs/xxx) to source path
        if (image_id or "").startswith("/outputs/"):
            source_path = _url_to_path(image_id, OUTPUT_DIR)
        else:
            source_path = _url_to_path(image_id, UPLOAD_DIR)
        if not source_path or not source_path.exists():
            raise HTTPException(status_code=400, detail="Invalid or missing image_id")
        # Resolve image_result URLs to file paths (individual_items only; flat_lay not stored in DB)
        item_urls = image_result.get("individual_items") or []
        item_paths = []
        for u in item_urls:
            p = _url_to_path(u, OUTPUT_DIR)
            item_paths.append(str(p) if p and p.exists() else None)
        resolved = {"flat_lay": "", "individual_items": item_paths}
        # Optional: associate try-on image if already generated (e.g. from lookbook before save)
        try_on_filename = None
        if try_on_url:
            try_on_path = _url_to_path(try_on_url.strip(), OUTPUT_DIR)
            if try_on_path and try_on_path.exists():
                try_on_filename = try_on_path.name
        outfit_id = persist_single_outfit(outfit, resolved, source_path, attributes, try_on_filename=try_on_filename)
        if outfit_id is None:
            raise HTTPException(status_code=500, detail="Failed to save outfit")
        return {"success": True, "id": outfit_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/outfits")
def get_saved_outfits(limit: int = 50):
    """List all saved looks for later reference. Most recent first."""
    try:
        outfits = list_outfits(limit=min(limit, 100))
        return {"success": True, "outfits": outfits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/outfits/{outfit_id}")
def delete_saved_outfit(outfit_id: int):
    """Delete a saved look by ID."""
    try:
        success = delete_outfit(outfit_id)
        if not success:
            raise HTTPException(status_code=404, detail="Outfit not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/outfits")
async def delete_all_outfits_endpoint():
    """Delete all saved looks."""
    try:
        success = delete_all_outfits()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete all outfits")
        return {"message": "All outfits deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
