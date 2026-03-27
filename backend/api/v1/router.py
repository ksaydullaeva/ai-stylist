from fastapi import APIRouter

from api.v1 import analyze, demo, outfits, pipeline, images, try_on, lens, home_feed

router = APIRouter(prefix="/api/v1")

router.include_router(analyze.router)
router.include_router(home_feed.router)
router.include_router(demo.router)
router.include_router(outfits.router)
router.include_router(pipeline.router)
router.include_router(images.router)
router.include_router(try_on.router)
router.include_router(lens.router)
