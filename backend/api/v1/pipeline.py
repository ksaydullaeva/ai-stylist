import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ai.captioning import analyze_wardrobe_item
from ai.appearance import analyze_user_appearance
from ai.suggestion import generate_outfit_suggestions
from repositories.outfit import persist_outfits
from services.pipeline import (
    UPLOAD_DIR,
    OUTPUT_DIR,
    get_image_generator,
    occasions_from_attributes,
    attach_image_urls,
)

router = APIRouter(tags=["pipeline"])


# ── Shared helpers ────────────────────────────────────────────────

async def _save_upload(upload: UploadFile, prefix: str = "") -> Path:
    ext = Path(upload.filename).suffix or ".jpg"
    filepath = UPLOAD_DIR / f"{prefix}{uuid.uuid4()}{ext}"
    filepath.write_bytes(await upload.read())
    return filepath


def _parse_occasions(occasions: str, attributes: dict) -> list[str]:
    if occasions and occasions.strip():
        return [o.strip() for o in occasions.split(",") if o.strip()]
    return occasions_from_attributes(attributes)


# ── Routes ────────────────────────────────────────────────────────

@router.post("/full-pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    occasions: str = "",
    user_photo: UploadFile = File(None),
):
    """Analyze → suggest → generate flat lays in one blocking call.
    Optional user_photo personalises suggestions by skin tone and hairstyle."""
    try:
        filepath = await _save_upload(file)

        attributes = analyze_wardrobe_item(str(filepath))
        if attributes.get("error") == "no_garment":
            raise HTTPException(
                status_code=400,
                detail=attributes.get("message", "The image does not appear to contain a clothing item."),
            )

        user_appearance = None
        if user_photo and user_photo.filename:
            user_filepath = await _save_upload(user_photo, prefix="user_")
            user_appearance = analyze_user_appearance(str(user_filepath))

        occasions_list = _parse_occasions(occasions, attributes)
        outfit_data = generate_outfit_suggestions(
            item_attributes=attributes,
            occasions=occasions_list,
            user_appearance=user_appearance,
        )

        outfits = outfit_data.get("outfits", []) or []
        generator = get_image_generator()
        image_results = generator.generate_all_outfits(
            outfit_data=outfit_data,
            output_dir=str(OUTPUT_DIR),
            source_image_path=str(filepath),
        )

        attach_image_urls(outfits, image_results)
        outfit_ids = persist_outfits(outfits, image_results, filepath, attributes)
        for i, o in enumerate(outfit_data.get("outfits", [])):
            if i < len(outfit_ids):
                o["id"] = outfit_ids[i]

        return {
            "success": True,
            "image_id": f"/uploads/{filepath.name}",
            "attributes": attributes,
            "outfits": outfit_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_pipeline(
    filepath: Path,
    occasions: str,
    user_filepath: Path | None,
):
    """Async generator — runs the full pipeline and yields NDJSON lines."""

    def emit(obj: dict) -> str:
        return json.dumps(obj) + "\n"

    try:
        yield emit({"type": "progress", "percent": 5, "message": "Saving image…"})

        attributes = await asyncio.to_thread(analyze_wardrobe_item, str(filepath))
        if attributes.get("error") == "no_garment":
            yield emit({
                "type": "error",
                "detail": attributes.get("message", "The image does not appear to contain a clothing item."),
            })
            return

        yield emit({"type": "progress", "percent": 15, "message": "Analyzing item…"})

        user_appearance = None
        if user_filepath and user_filepath.exists():
            yield emit({"type": "progress", "percent": 18, "message": "Analyzing your photo…"})
            user_appearance = await asyncio.to_thread(analyze_user_appearance, str(user_filepath))

        occasions_list = _parse_occasions(occasions, attributes)
        outfit_data = await asyncio.to_thread(
            generate_outfit_suggestions,
            item_attributes=attributes,
            occasions=occasions_list,
            user_appearance=user_appearance,
        )

        yield emit({"type": "progress", "percent": 35, "message": "Suggesting outfits…"})

        outfits = outfit_data.get("outfits", []) or []
        n_outfits = len(outfits)
        generator = get_image_generator()
        image_results = []

        for i in range(n_outfits):
            pct = 40 + int((i + 1) / n_outfits * 50) if n_outfits else 90
            yield emit({"type": "progress", "percent": pct, "message": f"Generating outfit {i + 1}/{n_outfits}…"})
            result = await asyncio.to_thread(
                generator.generate_full_suite,
                outfit_data, i, str(OUTPUT_DIR), str(filepath),
            )
            image_results.append({
                "flat_lay": result.get("flat_lay") or "",
                "individual_items": result.get("individual_items") or [],
            })

        attach_image_urls(outfits, image_results)

        yield emit({"type": "progress", "percent": 95, "message": "Saving…"})
        outfit_ids = await asyncio.to_thread(persist_outfits, outfits, image_results, filepath, attributes)
        for i, o in enumerate(outfit_data.get("outfits", [])):
            if i < len(outfit_ids):
                o["id"] = outfit_ids[i]

        yield emit({"type": "progress", "percent": 100, "message": "Done"})
        yield emit({
            "type": "result",
            "data": {
                "success": True,
                "image_id": f"/uploads/{filepath.name}",
                "attributes": attributes,
                "outfits": outfit_data,
            },
        })

    except Exception as e:
        yield emit({"type": "error", "detail": str(e)})


@router.post("/full-pipeline-stream")
async def full_pipeline_stream(
    file: UploadFile = File(...),
    occasions: str = "",
    user_photo: UploadFile = File(None),
):
    """Analyze → suggest → generate flat lays with streamed NDJSON progress.
    Optional user_photo personalises suggestions by skin tone and hairstyle."""
    try:
        filepath = await _save_upload(file)
        user_filepath = None
        if user_photo and user_photo.filename:
            user_filepath = await _save_upload(user_photo, prefix="user_")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        _stream_pipeline(filepath, occasions, user_filepath),
        media_type="application/x-ndjson",
    )
