"""
Gemini client helpers for text + vision requests.

Uses the new `google-genai` SDK (python-genai). This avoids truncation issues
observed with the deprecated `google.generativeai` package.
"""

from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from PIL import Image

from google import genai
from google.genai import types

from core.config import settings

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _get_google_api_key() -> str:
    # 1) pydantic settings (env + backend/.env)
    key = (settings.GOOGLE_API_KEY or "").strip()
    if key:
        return key

    # 2) dotenv (in case settings didn't load)
    env_path = _BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if key:
        return key

    # 3) direct read (avoid dotenv/pydantic quirks in Docker)
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_API_KEY=") and not line.startswith("GOOGLE_API_KEY=#"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key

    return ""


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    api_key = _get_google_api_key()
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not set. Add it to backend/.env or set the environment variable."
        )
    return genai.Client(api_key=api_key)


def _image_to_jpeg_bytes(image_path: str, max_size: int = 420, jpeg_quality: int = 90) -> bytes:
    """Load + downscale an image; returns JPEG bytes."""
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        resample = (
            getattr(Image, "Resampling", Image).LANCZOS
            if hasattr(Image, "Resampling")
            else Image.LANCZOS
        )
        img.thumbnail((max_size, max_size), resample=resample)

        import io

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        return buf.getvalue()


def _response_to_text(response: Any) -> str:
    text = getattr(response, "text", None)
    return text.strip() if isinstance(text, str) else ""


def extract_json_obj(raw_text: str) -> Optional[dict]:
    """Extract the first JSON object from model output."""
    clean_text = re.sub(r"```json|```", "", raw_text).strip()
    start_idx = clean_text.find("{")
    if start_idx == -1:
        return None

    last_idx = clean_text.rfind("}")
    if last_idx != -1 and last_idx > start_idx:
        candidate = clean_text[start_idx : last_idx + 1]
    else:
        candidate = clean_text[start_idx:]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def generate_text(
    prompt: str,
    *,
    model_name: str,
    temperature: float = 0.0,
    max_output_tokens: Optional[int] = None,
    response_mime_type: Optional[str] = None,
    timeout_s: Optional[float] = None,
) -> str:
    client = _get_client()
    t0 = time.time()
    try:
        if timeout_s is not None:
            pass

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_mime_type=response_mime_type,
            ),
        )
        return _response_to_text(response)
    finally:
        _ = time.time() - t0


def generate_vision_text(
    prompt: str,
    *,
    image_path: str,
    model_name: str,
    temperature: float = 0.0,
    max_output_tokens: Optional[int] = None,
    max_image_size: int = 420,
) -> str:
    client = _get_client()
    image_bytes = _image_to_jpeg_bytes(image_path, max_size=max_image_size)
    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    return _response_to_text(response)

