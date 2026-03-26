import urllib.parse
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from core.config import settings
from services.lens import query_similar_products, safe_rel_image_path

router = APIRouter(tags=["lens"])


@router.post("/lens/search")
async def lens_search(
    image: UploadFile = File(..., description="Product photo to search against Zara embeddings"),
    n: int = Query(12, ge=1, le=50, description="Number of results"),
    zara_category: str | None = Query(None, description="Optional filter like 'woman_blazers'"),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    # Save temp upload to uploads/ (same place as other endpoints)
    ext = Path(image.filename).suffix or ".jpg"
    tmp_path = settings.UPLOAD_DIR / f"lens_{Path(image.filename).stem}{ext}"
    tmp_path.write_bytes(await image.read())

    where = {"zara_category": zara_category} if zara_category else None
    try:
        res = query_similar_products(tmp_path, n_results=n, where=where)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    ids = (res.get("ids") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]

    out = []
    for i in range(min(len(ids), len(metas), len(dists))):
        md = metas[i] or {}
        rel = safe_rel_image_path(md.get("image_path") or "")
        image_url = f"/api/v1/lens/image?path={urllib.parse.quote(rel)}" if rel else None
        out.append(
            {
                "id": ids[i],
                "distance": float(dists[i]) if dists[i] is not None else None,
                "product_id": md.get("product_id"),
                "name": md.get("name"),
                "zara_category": md.get("zara_category"),
                "image_url": image_url,
                "image_path": md.get("image_path"),
                "document": docs[i] if i < len(docs) else md.get("chroma:document"),
            }
        )

    return {"success": True, "results": out}


@router.get("/lens/image")
async def lens_image(
    path: str = Query(..., description="Relative path under ZARA_DATASET_ROOT, URL-encoded"),
):
    # Decode and validate that the resulting path stays under the root.
    rel = urllib.parse.unquote(path).lstrip("/")
    root = Path(settings.ZARA_DATASET_ROOT).expanduser().resolve()
    full = (root / rel).resolve()
    try:
        full.relative_to(root)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(full))

