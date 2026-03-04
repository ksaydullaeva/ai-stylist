import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine
from models.orm import Outfit, OutfitItem  # noqa: F401 — registers ORM models
from api import health_router, v1_router
from services.pipeline import get_image_generator

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup; preload image generator in background."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(
            "Database not available: %s. "
            "Create the DB with: createdb styleai  (or set DATABASE_URL env var)",
            e,
        )

    async def preload_generator() -> None:
        await asyncio.to_thread(get_image_generator)
        logger.info("Image generator loaded")

    # Start preload in background so the server becomes ready immediately (fixes
    # Docker 502 while nginx waits). Only one thread creates the generator (lock in
    # get_image_generator); first request may wait on that if it runs before preload
    # finishes.
    task = asyncio.create_task(preload_generator())
    app.state.generator_preload_task = task
    logger.info("Image generator preload started in background")
    yield
    if not task.done():
        logger.warning("Generator preload never finished!")
    elif task.exception():
        logger.error("Generator preload failed: %s", task.exception())

app = FastAPI(title="StyleAI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(v1_router)
