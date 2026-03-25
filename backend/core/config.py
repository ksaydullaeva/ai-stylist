"""
Central application configuration.
All environment variables are read here; every other module imports from this file.
Set values in backend/.env or export them in the shell before starting the server.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg2://postgres@localhost:5432/styleai"

    # ── External APIs ────────────────────────────────────────────────
    GOOGLE_API_KEY: str = ""

    # ── Local Ollama models ──────────────────────────────────────────
    VISION_MODEL: str = "qwen2.5vl:3b"
    LLM_MODEL: str = "qwen2.5:3b"

    # ── Storage directories ──────────────────────────────────────────
    UPLOAD_DIR: Path = _BACKEND_DIR / "uploads"
    OUTPUT_DIR: Path = _BACKEND_DIR / "outputs"
    # Optional default person photos for try-on fallback when user_photo is omitted.
    # Can be overridden in backend/.env as absolute paths.
    DEFAULT_TRYON_MEN_PHOTO: str = "/Users/khurshida/.cursor/projects/Users-khurshida-python-projects-stylist-outfit-suggestion/assets/Screenshot_2026-03-12_at_10.32.48-aa6c3689-fc1c-4a3f-bfce-6ca41218fee7.png"
    DEFAULT_TRYON_WOMEN_PHOTO: str = "/Users/khurshida/.cursor/projects/Users-khurshida-python-projects-stylist-outfit-suggestion/assets/02075013251-p-4d87f74c-92a8-44af-a34f-a7eb26f4224c.png"

    # ── RAG dataset ──────────────────────────────────────────────────
    POLYVORE_JSON: Path = _BACKEND_DIR / "polyvore_converted.json"

    def ensure_dirs(self) -> None:
        self.UPLOAD_DIR.mkdir(exist_ok=True)
        self.OUTPUT_DIR.mkdir(exist_ok=True)


settings = Settings()
settings.ensure_dirs()
