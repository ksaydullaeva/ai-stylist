import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ai.captioning import analyze_wardrobe_item
from ai.appearance import validate_user_photo_for_tryon
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
        return {"success": True, "image_id": f"/uploads/{filepath.name}", "attributes": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-images")
async def validate_images(
    item: UploadFile = File(..., description="Garment/clothing item image"),
    user_photo: UploadFile = File(..., description="Full-body photo of the person"),
):
    """
    Validate that item image shows a garment and user_photo shows a full-body person.
    Returns item_ok, user_ok, and optional error messages.
    """
    item_path = None
    user_path = None
    try:
        item_path = await _save_upload(item, prefix="val_item_")
        user_path = await _save_upload(user_photo, prefix="val_user_")

        item_result = await asyncio.to_thread(analyze_wardrobe_item, str(item_path))
        item_ok = item_result.get("error") != "no_garment"
        item_message = None if item_ok else item_result.get("message", "The image does not appear to contain a clothing item.")

        user_result = await asyncio.to_thread(validate_user_photo_for_tryon, str(user_path))
        user_ok = user_result.get("ok") is True
        user_message = None if user_ok else user_result.get("message", "Please upload a full-body photo of yourself.")

        return {
            "item_ok": item_ok,
            "user_ok": user_ok,
            "item_message": item_message,
            "user_message": user_message,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in (item_path, user_path):
            if p and p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
