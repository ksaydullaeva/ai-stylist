from fastapi import APIRouter

from api.v1 import analyze, outfits, pipeline, images

router = APIRouter(prefix="/api/v1")

router.include_router(analyze.router)
router.include_router(outfits.router)
router.include_router(pipeline.router)
router.include_router(images.router)
