from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.pipeline import OUTPUT_DIR

router = APIRouter(tags=["images"])


@router.get("/images/{filename}")
def get_image(filename: str):
    """Serve a generated outfit image by filename."""
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path))
