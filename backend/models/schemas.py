from pydantic import BaseModel


class OutfitRequest(BaseModel):
    """Request body for POST /api/v1/outfit-suggestions."""
    item_attributes: dict
    occasions: list[str] = ["casual", "smart-casual"]


class PipelineResult(BaseModel):
    """Response shape for both /full-pipeline and /full-pipeline-stream (result event)."""
    success: bool
    image_id: str
    attributes: dict
    outfits: dict
