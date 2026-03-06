from fastapi import APIRouter

from api.v1 import analyze, outfits, pipeline, images, try_on

router = APIRouter(prefix="/api/v1")

router.include_router(analyze.router)
router.include_router(outfits.router)
router.include_router(pipeline.router)
router.include_router(images.router)
router.include_router(try_on.router)
