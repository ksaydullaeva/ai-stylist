import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ai.captioning import analyze_wardrobe_item
from ai.appearance import analyze_user_appearance
from ai.suggestion import generate_outfit_suggestions
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


def _image_results_to_urls(image_results: list) -> list[dict]:
    """Convert image_results (file paths) to URL form for the client (for save later)."""
    out = []
    for ir in image_results:
        flat = ir.get("flat_lay") or ""
        out.append({
            "flat_lay": f"/outputs/{Path(flat).name}" if flat else "",
            "individual_items": [f"/outputs/{Path(p).name}" for p in (ir.get("individual_items") or []) if p],
        })
    return out


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

        return {
            "success": True,
            "image_id": f"/uploads/{filepath.name}",
            "attributes": attributes,
            "outfits": outfit_data,
            "image_results": _image_results_to_urls(image_results),
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

        # Let the client render the outfit cards immediately (text first).
        # Images (item thumbnails / try-on inputs) stream in as individual outfits complete.
        yield emit({
            "type": "suggestions_ready",
            "data": {
                "success": True,
                "image_id": f"/uploads/{filepath.name}",
                "attributes": attributes,
                "outfits": outfit_data,
                "image_results": [],
            },
        })

        generator = get_image_generator()
        image_results = []

        for i in range(n_outfits):
            pct = 40 + int((i + 1) / n_outfits * 50) if n_outfits else 90
            yield emit({"type": "progress", "percent": pct, "message": f"Generating outfit {i + 1}/{n_outfits}…"})
            result = await asyncio.to_thread(
                generator.generate_full_suite,
                outfit_data, i, str(OUTPUT_DIR), str(filepath),
            )

            # Attach item image URLs for this outfit so the frontend can show it immediately.
            item_paths = result.get("individual_items") or []
            outfit = outfits[i]
            for j, item in enumerate(outfit.get("items", []) or []):
                if j < len(item_paths) and item_paths[j]:
                    item["image_url"] = f"/outputs/{Path(item_paths[j]).name}"

            # Also provide a URL-form image_result payload for saving later.
            flat = result.get("flat_lay") or ""
            flat_url = f"/outputs/{Path(flat).name}" if flat else ""
            individual_urls = [f"/outputs/{Path(p).name}" for p in (result.get("individual_items") or []) if p]
            image_result = {
                "flat_lay": flat_url,
                "individual_items": individual_urls,
            }

            image_results.append({
                "flat_lay": result.get("flat_lay") or "",
                "individual_items": result.get("individual_items") or [],
            })

            yield emit({
                "type": "outfit_ready",
                "data": {
                    "index": i,
                    "outfit": outfit,
                    "image_result": image_result,
                },
            })

        attach_image_urls(outfits, image_results)

        yield emit({"type": "progress", "percent": 100, "message": "Done"})
        yield emit({
            "type": "result",
            "data": {
                "success": True,
                "image_id": f"/uploads/{filepath.name}",
                "attributes": attributes,
                "outfits": outfit_data,
                "image_results": _image_results_to_urls(image_results),
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
