"""
Virtual try-on API: person photo + outfit (with generated item images) → try-on image.

Source garment = the initial clothing item image the user uploaded at the start
(the same image they sent, along with their optional self photo, to get outfit suggestions).
"""

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from repositories.outfit import update_outfit_try_on
from services.pipeline import OUTPUT_DIR, UPLOAD_DIR, get_image_generator

router = APIRouter(tags=["try-on"])


async def _save_upload(upload: UploadFile, prefix: str = "") -> Path:
    ext = Path(upload.filename).suffix or ".jpg"
    filepath = UPLOAD_DIR / f"{prefix}{uuid.uuid4()}{ext}"
    filepath.write_bytes(await upload.read())
    return filepath


@router.post("/try-on")
async def try_on(
    user_photo: UploadFile = File(..., description="Photo of the person (full or upper body)"),
    outfit: str = File(..., description="JSON: { \"items\": [{\"type\", \"color\", \"image_url\"}], \"style_title\"?, \"gender_context\"? }"),
    garment_image: UploadFile = File(None, description="Source garment: the initial clothing item image the user sent (with their optional self image)"),
    outfit_id: int | None = Form(None, description="Optional: DB outfit ID to save try-on image for later reference"),
    gender: str | None = Form(None, description="Optional: 'men' or 'women' for default fashion pose (overrides outfit.gender_context)"),
):
    """Generate a try-on image: person wearing the given outfit using Gemini 2.5 Flash.

    - user_photo: photo of the person (their optional self image from the initial flow, or uploaded in try-on).
    - outfit: JSON string with keys:
      - items: list of { type, color, image_url } where image_url is the filename (e.g. from /api/v1/images/xxx.jpg).
      - style_title (optional): for description.
    - garment_image: source garment = the initial image of the clothing item the user uploaded at the start
      (the same item they sent with their optional self image). When provided, try-on uses it so the model sees the actual piece.

    Returns: { "try_on_url": "/outputs/<filename>" }
    """
    if not user_photo.filename or not user_photo.content_type or not user_photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file as user_photo")

    try:
        payload = json.loads(outfit)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid outfit JSON: {e}")

    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="outfit.items cannot be empty")

    # Gender for default fashion pose: explicit form param or from outfit payload
    try_on_gender = gender.strip() if gender else None
    if not try_on_gender:
        try_on_gender = (payload.get("gender_context") or "").strip() or None
    if try_on_gender:
        try_on_gender = try_on_gender.lower()
        if try_on_gender == "male":
            try_on_gender = "men"
        elif try_on_gender == "female":
            try_on_gender = "women"
        if try_on_gender not in ("men", "women"):
            try_on_gender = None

    # Resolve image_url (filename only) to full paths under OUTPUT_DIR
    item_paths: list[str] = []
    for it in items:
        url = it.get("image_url") or ""
        # Allow "/outputs/foo.jpg" or "foo.jpg"
        filename = url.split("/")[-1] if "/" in url else url
        if not filename:
            continue
        path = OUTPUT_DIR / filename
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Outfit image not found: {filename}. Generate outfit images first.",
            )
        item_paths.append(str(path))

    if not item_paths:
        raise HTTPException(status_code=400, detail="No valid outfit item images found")

    # Build short description from items; when source garment is used, prepend anchor so try-on includes it
    desc_parts = [f"{it.get('color', '')} {it.get('type', '')}".strip() for it in items]
    outfit_description = ", ".join(p for p in desc_parts if p) or "outfit"
    anchor_item = (payload.get("anchor_item") or "").strip()
    if anchor_item and garment_image and garment_image.filename:
        full_outfit_description = f"{anchor_item}, {outfit_description}"
    else:
        full_outfit_description = outfit_description

    # Save uploaded person photo
    person_path = await _save_upload(user_photo, prefix="tryon_person_")
    garment_path = None
    if garment_image and garment_image.filename and garment_image.content_type and garment_image.content_type.startswith("image/"):
        garment_path = await _save_upload(garment_image, prefix="tryon_garment_")

    try:
        generator = get_image_generator()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_filename = f"tryon_{uuid.uuid4().hex[:8]}.jpg"
        output_path = OUTPUT_DIR / out_filename

        result_path = await asyncio.to_thread(
            generator.try_on,
            str(person_path),
            item_paths,
            full_outfit_description,
            str(output_path),
            source_garment_path=str(garment_path) if garment_path else None,
            anchor_description=anchor_item or None,
            gender=try_on_gender,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if person_path.exists():
            try:
                person_path.unlink()
            except OSError:
                pass
        if garment_path and garment_path.exists():
            try:
                garment_path.unlink()
            except OSError:
                pass

    if not result_path:
        raise HTTPException(status_code=502, detail="Try-on image generation failed")

    try_on_filename = Path(result_path).name
    if outfit_id is not None:
        update_outfit_try_on(outfit_id, try_on_filename)

    return {"try_on_url": f"/outputs/{try_on_filename}"}
