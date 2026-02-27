import base64
import io
import json
import re
import time
from typing import Any, Dict

import ollama
from PIL import Image


def encode_image(image_path: str) -> str:
    """Load and downscale an image, returning a base64-encoded string."""
    with Image.open(image_path) as img:
        img.thumbnail((300, 300))  # 224-fabric is not clear
        buffer = io.BytesIO()
        img_format = img.format if img.format else "PNG"
        img.save(buffer, format=img_format, quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyze_wardrobe_item(image_path: str) -> Dict[str, Any]:
    """Run vision model on a wardrobe item and return structured attributes."""
    total_start = time.time()

    start = time.time()
    image_data = encode_image(image_path)
    print(f"[TIMER] image encoding total: {time.time() - start:.4f}s")

    prompt = """You are a Fashion Expert. First, decide if this image shows a WEARABLE GARMENT (clothing item) such as a top, jacket, pants, skirt, dress, shoes, accessory, etc. — either on a person, on a mannequin, or as a product/flat lay.

    If the image does NOT show a clothing item (e.g. it shows a landscape, animal, face only, car, food, random object, or scene with no visible garment), respond with ONLY this exact JSON and nothing else:
    {"error": "no_garment", "message": "The image does not appear to contain a clothing item. Please upload a photo of a garment."}

    If the image DOES show a wearable garment, analyze it and return a structured description. COLOR DETECTION IS CRITICAL. Look very carefully:
    - Navy blue and black are DIFFERENT colors. Navy blue has a blue undertone.
    - Dark colors: navy blue, charcoal, dark brown, burgundy, forest green
    - Never default to "black" — examine the hue carefully under the assumption 
    that the item may be a dark version of another color.

    Extract the following details:
    - item_type
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
        model="qwen2.5vl:3b",
        options={
            "num_ctx": 1024,
            "num_predict": 120,  # limit tokens
            "temperature": 0.0,
            # "top_k": 20,
            # "top_p": 0.9,
        },
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [image_data],
            }
        ],
    )
    print(f"[TIMER] ollama.chat took {time.time() - start:.4f}s")

    raw_text = response["message"]["content"]
    print(raw_text)

    # JSON extraction from LLM response
    try:
        clean_text = re.sub(r"```json|```", "", raw_text).strip()
        start_idx = clean_text.find("{")
        if start_idx == -1:
            raise ValueError("No JSON braces found in response")

        json_payload = clean_text[start_idx:]
        decoder = json.JSONDecoder()
        parsed, _ = decoder.raw_decode(json_payload)

        print(
            f"[TIMER] TOTAL item captioning process took "
            f"{time.time() - total_start:.4f}s"
        )
        return parsed

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Parsing Error: {e}")
        return {"raw_output": raw_text, "error": "Could not parse JSON"}
