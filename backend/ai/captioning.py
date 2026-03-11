"""Vision-based garment attribute extraction using a local Ollama model."""

import base64
import io
import json
import re
import time
from typing import Any, Dict

import ollama
from PIL import Image

from core.config import settings


def _encode_image(image_path: str, max_size: int = 300) -> str:
    """Downscale and base64-encode an image for the vision model."""
    with Image.open(image_path) as img:
        img.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        img_format = img.format if img.format else "PNG"
        img.save(buffer, format=img_format, quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyze_wardrobe_item(image_path: str) -> Dict[str, Any]:
    """Run the vision model on a garment image; return structured attributes dict."""
    total_start = time.time()

    start = time.time()
    image_data = _encode_image(image_path)
    print(f"[TIMER] image encoding: {time.time() - start:.4f}s")

    prompt = """You are a Fashion Expert. First, decide if this image shows a WEARABLE GARMENT (clothing item) such as a top, jacket, pants, skirt, dress, shoes, accessory, etc. — either on a person, on a mannequin, or as a product/flat lay.

    If the image does NOT show a clothing item (e.g. it shows a landscape, animal, face only, car, food, random object, or scene with no visible garment), respond with ONLY this exact JSON and nothing else:
    {"error": "no_garment", "message": "The image does not appear to contain a clothing item. Please upload a photo of a garment."}

    If the image DOES show a wearable garment, analyze it and return a structured description. COLOR DETECTION IS CRITICAL. Look very carefully:
    - Navy blue and black are DIFFERENT colors. Navy blue has a blue undertone.
    - Dark colors: navy blue, charcoal, dark brown, burgundy, forest green
    - Never default to "black" — examine the hue carefully under the assumption
    that the item may be a dark version of another color.

    Extract the following details:
    - item_type (e.g. jeans, blouse, jacket, sneakers)
    - category: MUST be exactly one of "top", "bottom", "shoes", "accessory", "outerwear"
      (top=shirts/blouses/sweaters/tanks; bottom=pants/jeans/skirts/shorts; shoes=footwear; accessory=bag/belt/hat/jewelry; outerwear=jacket/coat/blazer)
    - gender: women or men
    - age_group: must be ONE of these exact values:
        * "kids"       → under 12, small sizing, playful designs, cartoon prints
        * "teen"       → 13-17, trendy, streetwear leaning, crop tops, graphic tees
        * "adult"      → 18-45, professional, fashion-forward, wide variety
        * "mature"     → 45+, classic cuts, modest lengths, comfortable fits
        * "unisex-all" → genuinely age-neutral basics (plain white tee, socks, etc.)
    - color: primary and secondary colors
    - pattern
    - fit
    - style_category
    - material_guess
    - season
    - tags

    Respond ONLY with a valid JSON object (either the error object above or the structured description)."""

    start = time.time()
    response = ollama.chat(
        model=settings.VISION_MODEL,
        options={
            "num_ctx": 1024,
            "num_predict": 120,
            "temperature": 0.0,
        },
        messages=[{"role": "user", "content": prompt, "images": [image_data]}],
    )
    print(f"[TIMER] ollama.chat: {time.time() - start:.4f}s")

    raw_text = response["message"]["content"]
    print(raw_text)

    try:
        clean_text = re.sub(r"```json|```", "", raw_text).strip()
        start_idx = clean_text.find("{")
        if start_idx == -1:
            raise ValueError("No JSON object found in response")
        parsed, _ = json.JSONDecoder().raw_decode(clean_text[start_idx:])
        print(f"[TIMER] TOTAL captioning: {time.time() - total_start:.4f}s")
        return parsed
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Parsing error: {e}")
        return {"raw_output": raw_text, "error": "Could not parse JSON"}
