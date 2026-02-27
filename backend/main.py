from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import Base, engine
from models import Outfit, OutfitImage, OutfitItem  # ensure models are registered
from routers import api_router, health_router


app = FastAPI(title="StyleAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables on startup (simple auto-migration)."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "Database not available: %s. Create the DB with: createdb styleai (or set DATABASE_URL)", e
        )


# ── Routers ───────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(api_router)
