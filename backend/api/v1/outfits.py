from fastapi import APIRouter, HTTPException

from ai.suggestion import generate_outfit_suggestions
from models.schemas import OutfitRequest
from repositories.outfit import list_outfits, delete_outfit, delete_all_outfits

router = APIRouter(tags=["outfits"])


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


@router.get("/outfits")
def get_saved_outfits(limit: int = 50):
    """List all saved outfits (generated lookbooks) for later reference. Most recent first."""
    try:
        outfits = list_outfits(limit=min(limit, 100))
        return {"success": True, "outfits": outfits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/outfits/{outfit_id}")
def delete_saved_outfit(outfit_id: int):
    """Delete a saved outfit by ID."""
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
    """Delete all saved outfits."""
    try:
        success = delete_all_outfits()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete all outfits")
        return {"message": "All outfits deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
