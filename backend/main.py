import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from services.pipeline import OUTPUT_DIR, UPLOAD_DIR

from core.database import Base, engine
from models.orm import Outfit, OutfitItem  # noqa: F401 — registers ORM models
from api import health_router, v1_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup; add new columns if missing."""
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE outfits ADD COLUMN IF NOT EXISTS try_on_image_path VARCHAR(512)"))
            conn.commit()
    except Exception as e:
        logger.warning(
            "Database not available: %s. "
            "Create the DB with: createdb styleai  (or set DATABASE_URL env var)",
            e,
        )

    yield

app = FastAPI(title="StyleAI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(v1_router)

# Serve generated images and user uploads
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
