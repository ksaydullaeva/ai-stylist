import asyncio
import json
import uuid
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from db import SessionLocal
from models import Outfit, OutfitImage, OutfitItem
from image_generator_api_advanced import OutfitImageGenerator
from item_captioning import analyze_wardrobe_item
from outfit_suggestion import generate_outfit_suggestions


UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@lru_cache(maxsize=1)
def get_image_generator() -> OutfitImageGenerator:
    return OutfitImageGenerator()


router = APIRouter(prefix="/api")


# ── Pydantic Models ──────────────────────────────────────────────
class OutfitRequest(BaseModel):
    item_attributes: dict
    occasions: list[str] = ["casual", "smart-casual"]


class GenerateImageRequest(BaseModel):
    outfit_data: dict
    outfit_index: int = 0


# ── Routes ───────────────────────────────────────────────────────
@router.post("/analyze")
async def analyze_item(file: UploadFile = File(...)):
    """Step 1 — Upload image and extract item attributes."""
    try:
        ext = Path(file.filename).suffix or ".jpg"
        filename = f"{uuid.uuid4()}{ext}"
        filepath = UPLOAD_DIR / filename

        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        result = analyze_wardrobe_item(str(filepath))
        if result.get("error") == "no_garment":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "The image does not appear to contain a clothing item. Please upload a photo of a garment."),
            )

        return {"success": True, "image_id": filename, "attributes": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outfit-suggestions")
def get_outfit_suggestions(req: OutfitRequest):
    """Step 2 — Generate outfit suggestions from item attributes."""
    try:
        result = generate_outfit_suggestions(
            item_attributes=req.item_attributes,
            occasions=req.occasions,
        )
        return {"success": True, "outfits": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/image/{filename}")
def get_image(filename: str):
    """Serve generated flat lay images."""
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path))


def _occasions_from_attributes(attributes: dict) -> list[str]:
    """Derive occasion list from image captioning attributes when user leaves occasions blank."""
    result = []
    if attributes.get("style_category"):
        sc = attributes["style_category"]
        result.append(sc if isinstance(sc, str) else str(sc))
    tags = attributes.get("tags")
    if isinstance(tags, list):
        for t in tags:
            if t and (t not in result):
                result.append(t if isinstance(t, str) else str(t))
                if len(result) >= 3:
                    break
    if not result:
        result = ["casual", "smart-casual"]
    return result


def _persist_outfits_sync(
    outfits: list,
    image_results: list,
    filepath: Path,
    attributes: dict,
) -> None:
    """Sync helper to persist outfits to DB (for use in executor)."""
    session = SessionLocal()
    try:
        for idx, outfit in enumerate(outfits):
            db_outfit = Outfit(
                occasion=outfit.get("occasion", ""),
                style_title=outfit.get("style_title", ""),
                style_notes=outfit.get("style_notes", ""),
                color_palette=",".join(outfit.get("color_palette", [])),
                source_image_path=str(filepath),
                attributes=attributes,
            )
            session.add(db_outfit)
            session.flush()
            if idx < len(image_results) and image_results[idx].get("flat_lay"):
                session.add(
                    OutfitImage(
                        outfit_id=db_outfit.id,
                        kind="flatlay",
                        image_path=image_results[idx]["flat_lay"],
                    )
                )
            item_fs_paths = (
                image_results[idx].get("individual_items") or []
                if idx < len(image_results) else []
            )
            for j, item in enumerate(outfit.get("items", [])):
                session.add(
                    OutfitItem(
                        outfit_id=db_outfit.id,
                        category=item.get("category"),
                        color=item.get("color"),
                        type=item.get("type"),
                        description=item.get("description"),
                        likely_owned=bool(item.get("likely_owned")),
                        shopping_keywords=item.get("shopping_keywords"),
                        image_path=item_fs_paths[j] if j < len(item_fs_paths) else None,
                    )
                )
        session.commit()
    except Exception as e:
        session.rollback()
        import logging
        logging.getLogger("uvicorn.error").warning("Could not persist to database: %s", e)
    finally:
        session.close()


@router.post("/full-pipeline")
async def full_pipeline(
    file: UploadFile = File(...),
    occasions: str = "",
):
    """Run full pipeline: analyze → suggest outfits → generate flatlays and persist.
    If occasions is blank, occasions are predicted from image captioning (style_category, tags)."""
    try:
        ext = Path(file.filename).suffix or ".jpg"
        filename = f"{uuid.uuid4()}{ext}"
        filepath = UPLOAD_DIR / filename
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        attributes = analyze_wardrobe_item(str(filepath))
        if attributes.get("error") == "no_garment":
            raise HTTPException(
                status_code=400,
                detail=attributes.get("message", "The image does not appear to contain a clothing item. Please upload a photo of a garment."),
            )
        if occasions and occasions.strip():
            occasions_list = [o.strip() for o in occasions.split(",") if o.strip()]
        else:
            occasions_list = _occasions_from_attributes(attributes)
        outfit_data = generate_outfit_suggestions(
            item_attributes=attributes,
            occasions=occasions_list,
        )

        outfits = outfit_data.get("outfits", []) or []

        # Generate flatlays and individual item images for all outfits
        generator: OutfitImageGenerator = get_image_generator()
        image_results = generator.generate_all_outfits(
            outfit_data=outfit_data,
            output_dir=str(OUTPUT_DIR),
            source_image_path=str(filepath),
        )

        flatlay_urls = []
        for res in image_results:
            flat_lay = res.get("flat_lay")
            if flat_lay:
                flatlay_urls.append(f"/api/image/{Path(flat_lay).name}")

        # Attach individual item image URLs to each outfit's items (same order as items)
        for idx, outfit in enumerate(outfits):
            items = outfit.get("items", [])
            if idx < len(image_results):
                item_paths = image_results[idx].get("individual_items") or []
                for j, item in enumerate(items):
                    if j < len(item_paths) and item_paths[j]:
                        item["image_url"] = f"/api/image/{Path(item_paths[j]).name}"

        # Persist outfits, items, and images to Postgres
        _persist_outfits_sync(outfits, image_results, filepath, attributes)

        # For backward compatibility, return first image URL plus all flatlays
        first_image_url = flatlay_urls[0] if flatlay_urls else None

        return {
            "success": True,
            "image_id": filename,
            "attributes": attributes,
            "outfits": outfit_data,
            "image_url": first_image_url,
            "flatlay_image_urls": flatlay_urls,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _full_pipeline_stream_gen(filepath: Path, filename: str, occasions: str):
    """Async generator that runs the full pipeline and yields NDJSON progress/result lines."""
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

        if occasions and occasions.strip():
            occasions_list = [o.strip() for o in occasions.split(",") if o.strip()]
        else:
            occasions_list = _occasions_from_attributes(attributes)
        outfit_data = await asyncio.to_thread(
            generate_outfit_suggestions,
            item_attributes=attributes,
            occasions=occasions_list,
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
                outfit_data,
                i,
                str(OUTPUT_DIR),
                str(filepath),
            )
            image_results.append({
                "flat_lay": result.get("flat_lay") or "",
                "individual_items": result.get("individual_items") or [],
            })

        flatlay_urls = []
        for res in image_results:
            flat_lay = res.get("flat_lay")
            if flat_lay:
                flatlay_urls.append(f"/api/image/{Path(flat_lay).name}")

        for idx, outfit in enumerate(outfits):
            items = outfit.get("items", [])
            if idx < len(image_results):
                item_paths = image_results[idx].get("individual_items") or []
                for j, item in enumerate(items):
                    if j < len(item_paths) and item_paths[j]:
                        item["image_url"] = f"/api/image/{Path(item_paths[j]).name}"

        yield emit({"type": "progress", "percent": 95, "message": "Saving…"})
        await asyncio.to_thread(
            _persist_outfits_sync,
            outfits,
            image_results,
            filepath,
            attributes,
        )

        first_image_url = flatlay_urls[0] if flatlay_urls else None
        result_payload = {
            "success": True,
            "image_id": filename,
            "attributes": attributes,
            "outfits": outfit_data,
            "image_url": first_image_url,
            "flatlay_image_urls": flatlay_urls,
        }
        yield emit({"type": "progress", "percent": 100, "message": "Done"})
        yield emit({"type": "result", "data": result_payload})

    except Exception as e:
        yield emit({"type": "error", "detail": str(e)})


@router.post("/full-pipeline-stream")
async def full_pipeline_stream(
    file: UploadFile = File(...),
    occasions: str = "",
):
    """Run full pipeline and stream progress as NDJSON (progress + result)."""
    try:
        ext = Path(file.filename).suffix or ".jpg"
        filename = f"{uuid.uuid4()}{ext}"
        filepath = UPLOAD_DIR / filename
        contents = await file.read()
        filepath.write_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        _full_pipeline_stream_gen(filepath, filename, occasions),
        media_type="application/x-ndjson",
    )
