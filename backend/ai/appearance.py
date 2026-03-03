"""
Optional user-appearance analysis for context-aware outfit recommendations.
Extracts skin tone, hairstyle, and other visible attributes from a selfie.
"""

import base64
import io
import json
import re
from typing import Any, Dict

import ollama
from PIL import Image

from core.config import settings


def _encode_image(image_path: str, max_size: int = 400) -> str:
    with Image.open(image_path) as img:
        img.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        img_format = img.format if img.format else "PNG"
        img.save(buffer, format=img_format, quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyze_user_appearance(image_path: str) -> Dict[str, Any]:
    """
    Analyze a selfie for styling context.
    Returns a dict with skin_tone, undertone, hairstyle, hair_color, face_shape, general_notes.
    If no person is detected, returns {"error": "no_person", "message": "..."}.
    """
    image_data = _encode_image(image_path)

    prompt = """You are a fashion and style expert. Look at this image and decide if it shows a PERSON (face/portrait/selfie or full body).
If the image does NOT show a person (e.g. only clothing, object, landscape, or no clear face), respond with ONLY this JSON and nothing else:
{"error": "no_person", "message": "No person detected. This feature works best with a photo of yourself."}

If the image DOES show a person, analyze their appearance for styling recommendations. Extract:
- skin_tone: one of "fair", "light", "medium", "olive", "tan", "brown", "dark" or a short phrase (e.g. "warm medium")
- undertone: "cool", "warm", or "neutral" if visible
- hairstyle: brief description (e.g. "short dark hair", "long wavy blonde", "curly black")
- hair_color: if clearly visible
- body_type: f.e Hourglass, Pear (Triangle), Apple (Inverted Triangle), Rectangle (Straight), Spoon (Diamond)
- face_shape: only if clearly visible: "oval", "round", "square", "heart", "oblong" or skip
- general_notes: one short sentence of styling-relevant notes (e.g. "glasses, casual setting")

Respond ONLY with a valid JSON object. No markdown, no extra text."""

    try:
        response = ollama.chat(
            model=settings.VISION_MODEL,
            options={"num_ctx": 1024, "num_predict": 150, "temperature": 0.0},
            messages=[{"role": "user", "content": prompt, "images": [image_data]}],
        )
    except Exception as e:
        return {"error": "analysis_failed", "message": str(e)}

    raw_text = response["message"]["content"]

    try:
        clean_text = re.sub(r"```json|```", "", raw_text).strip()
        start_idx = clean_text.find("{")
        if start_idx == -1:
            return {}
        parsed, _ = json.JSONDecoder().raw_decode(clean_text[start_idx:])
        if parsed.get("error") == "no_person":
            return parsed
        return {k: v for k, v in parsed.items() if k not in ("error", "message") and v is not None}
    except (json.JSONDecodeError, ValueError):
        return {"raw_output": raw_text}
