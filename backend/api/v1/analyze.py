import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ai.captioning import analyze_wardrobe_item
from services.pipeline import UPLOAD_DIR

router = APIRouter(tags=["analyze"])


async def _save_upload(upload: UploadFile, prefix: str = "") -> Path:
    ext = Path(upload.filename).suffix or ".jpg"
    filepath = UPLOAD_DIR / f"{prefix}{uuid.uuid4()}{ext}"
    filepath.write_bytes(await upload.read())
    return filepath


@router.post("/analyze")
async def analyze_item(file: UploadFile = File(...)):
    """Upload a garment image and extract structured item attributes."""
    try:
        filepath = await _save_upload(file)
        result = analyze_wardrobe_item(str(filepath))
        if result.get("error") == "no_garment":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "The image does not appear to contain a clothing item."),
            )
        return {"success": True, "image_id": filepath.name, "attributes": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
