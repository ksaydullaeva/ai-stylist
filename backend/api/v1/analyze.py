import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ai.captioning import analyze_wardrobe_item
from ai.appearance import validate_user_photo_for_tryon
from ai.validators import validate_item_photo_for_trimming, validate_user_photo_for_outfit_fit
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
        item_error = None if item_ok else item_result.get("error") or "no_garment"
        item_message = None if item_ok else item_result.get("message", "The image does not appear to contain a clothing item.")

        # Step 1 ("Clothing Item") should be a garment/product image.
        # If the item upload looks like a full-body person, it's *likely* the user reversed steps,
        # but only treat it as swapped if Step 2 validation is also failing.
        item_person_result = await asyncio.to_thread(validate_user_photo_for_tryon, str(item_path))

        user_result = await asyncio.to_thread(validate_user_photo_for_tryon, str(user_path))
        user_ok = user_result.get("ok") is True
        user_error = None if user_ok else user_result.get("error") or "invalid_user_photo"
        user_message = None if user_ok else user_result.get("message", "Please upload a full-body photo of yourself.")

        if item_ok and item_person_result.get("ok") is True and not user_ok:
            item_ok = False
            item_error = item_person_result.get("error") or "swapped_steps"
            item_message = (
                "This image looks like a full-body photo of a person. "
                "For 'Clothing Item', please upload the garment/product image (not a full-body portrait). "
                "If you uploaded them reversed, switch the photos between Step 1 and Step 2."
            )

        return {
            "item_ok": item_ok,
            "user_ok": user_ok,
            "item_error": item_error,
            "user_error": user_error,
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


@router.post("/validate-item")
async def validate_item(
    item: UploadFile = File(..., description="Garment/clothing item image"),
):
    """
    Step 1 validation only: validate that `item` looks like a garment.
    Returns: { item_ok: bool, item_error?: str, item_message?: str }
    """
    item_path = None
    try:
        item_path = await _save_upload(item, prefix="val_item_")
        # 1) Make sure it's a garment at all.
        item_result = await asyncio.to_thread(analyze_wardrobe_item, str(item_path))
        item_ok = item_result.get("error") != "no_garment"
        item_error = None if item_ok else item_result.get("error") or "no_garment"
        item_message = None if item_ok else item_result.get("message", "Please upload a clear photo of a single clothing item.")

        # 2) If it is a garment, ensure it's clear enough for trimming/segmentation.
        if item_ok:
            quality = await asyncio.to_thread(validate_item_photo_for_trimming, str(item_path))
            if quality.get("ok") is not True:
                item_ok = False
                item_error = quality.get("error") or "invalid_item_photo"
                item_message = quality.get("message") or "Please upload a clearer item photo for trimming."

        # Helpful swapped-step hint: if it looks like a full-body person, Step 1 is likely wrong.
        if not item_ok and item_error in ("no_garment", "invalid_item_photo", "cropped_item", "too_small"):
            person_result = await asyncio.to_thread(validate_user_photo_for_outfit_fit, str(item_path))
            if person_result.get("ok") is True:
                item_error = "swapped_steps"
                item_message = (
                    "This image looks like a full-body photo of a person. "
                    "For 'Clothing Item' (Step 1), please upload the garment/product image (not a portrait). "
                    "If you uploaded them reversed, switch the photos between Step 1 and Step 2."
                )

        return {
            "item_ok": item_ok,
            "item_error": item_error,
            "item_message": item_message,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if item_path and item_path.exists():
            try:
                item_path.unlink()
            except OSError:
                pass


@router.post("/validate-user-photo")
async def validate_user_photo(
    user_photo: UploadFile = File(..., description="Full-body photo of the person"),
):
    """
    Step 2 validation only: validate that `user_photo` looks like a person full-body photo.
    Returns: { user_ok: bool, user_error?: str, user_message?: str }
    """
    user_path = None
    try:
        user_path = await _save_upload(user_photo, prefix="val_user_")
        user_result = await asyncio.to_thread(validate_user_photo_for_outfit_fit, str(user_path))
        user_ok = user_result.get("ok") is True
        user_error = None if user_ok else user_result.get("error") or "invalid_user_photo"
        user_message = None if user_ok else user_result.get("message", "Please upload a full-body photo of yourself.")

        # If the model thinks there's no person, it's a strong sign Step 2 image is actually the garment (swapped).
        if not user_ok and user_error == "no_person":
            # Double-check garment-ness to reduce false swaps.
            item_like = await asyncio.to_thread(analyze_wardrobe_item, str(user_path))
            if item_like.get("error") != "no_garment":
                user_error = "swapped_steps"
            user_message = (
                "This image doesn't look like a full-body photo of you. "
                "For 'Full-body Image' (Step 2), please upload a head-to-toe full-body photo of yourself. "
                "If you uploaded them reversed, switch the photos between Step 1 and Step 2."
            )

        return {
            "user_ok": user_ok,
            "user_error": user_error,
            "user_message": user_message,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if user_path and user_path.exists():
            try:
                user_path.unlink()
            except OSError:
                pass
