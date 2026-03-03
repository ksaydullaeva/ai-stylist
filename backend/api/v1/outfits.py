from fastapi import APIRouter, HTTPException

from ai.suggestion import generate_outfit_suggestions
from models.schemas import OutfitRequest

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
