import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine
from models.orm import Outfit, OutfitItem  # noqa: F401 — registers ORM models
from api import health_router, v1_router

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
