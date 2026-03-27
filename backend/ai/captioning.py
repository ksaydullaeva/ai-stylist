"""Vision-based garment attribute extraction using Gemini."""

import time
from typing import Any, Dict

from ai.gemini_client import extract_json_obj, generate_vision_text

from core.config import settings


def analyze_wardrobe_item(image_path: str) -> Dict[str, Any]:
    """Run the vision model on a garment image; return structured attributes dict."""
    total_start = time.time()

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
    - category: MUST be exactly one of "top", "bottom", "dress", "shoes", "outerwear", at least 2 of "accessory"
      (top=shirts/blouses/sweaters/tanks; bottom=pants/jeans/skirts/shorts; dress=one-piece dresses (midi/mini/maxi)/jumpsuits/rompers; shoes=footwear; accessory=bag/belt/hat/jewelry; outerwear=jacket/coat/blazer)
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
    raw_text = generate_vision_text(
        prompt,
        image_path=image_path,
        model_name=settings.VISION_MODEL,
        temperature=0.0,
        max_output_tokens=900,
        max_image_size=300,
    )
    print(f"[TIMER] gemini.generate_vision_text: {time.time() - start:.4f}s")

    print(raw_text)

    parsed = extract_json_obj(raw_text)
    if parsed is None:
        return {"raw_output": raw_text, "error": "Could not parse JSON"}

    print(f"[TIMER] TOTAL captioning: {time.time() - total_start:.4f}s")
    return parsed
