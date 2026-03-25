"""
Vision-based validators for user uploads.

These validators are stricter than general classification:
- Item photo: ensure garment is clear and fully visible for trimming/segmentation.
- User photo: ensure full-body visibility and avoid heavy outerwear that hides body structure.
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any, Dict

import ollama
from PIL import Image

from core.config import settings


def _encode_image(image_path: str, max_size: int = 420) -> str:
    with Image.open(image_path) as img:
        img.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        img_format = img.format if img.format else "PNG"
        img.save(buffer, format=img_format, quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _parse_json(raw_text: str) -> Dict[str, Any]:
    clean_text = re.sub(r"```json|```", "", raw_text).strip()
    start_idx = clean_text.find("{")
    if start_idx == -1:
        return {"error": "invalid_response", "message": "Could not validate image."}
    last_idx = clean_text.rfind("}")
    if last_idx != -1 and last_idx > start_idx:
        clean_text = clean_text[start_idx:last_idx + 1]
    else:
        clean_text = clean_text[start_idx:]
    try:
        parsed, _ = json.JSONDecoder().raw_decode(clean_text)
        if isinstance(parsed, dict):
            return parsed
        return {"error": "invalid_response", "message": "Could not validate image."}
    except (json.JSONDecodeError, ValueError):
        return {"error": "invalid_response", "message": "Could not validate image."}


def validate_item_photo_for_trimming(image_path: str) -> Dict[str, Any]:
    """
    Validate Step 1 item photo quality for trimming/segmentation.

    Returns:
      - {"ok": True}
      - {"error": "<code>", "message": "<user-facing>"} where code is one of:
        "no_garment", "too_blurry", "too_dark", "too_small", "cropped_item",
        "busy_background", "occluded_item", "multiple_items", "invalid_response"
    """
    image_data = _encode_image(image_path)
    prompt = """You are validating an upload for a fashion app.
Answer with ONLY a JSON object, nothing else.

    Goal: the image must be suitable for accurately trimming/segmenting ONE garment's edges.

Rules:
1) If the image does NOT clearly show a wearable garment/product (e.g. landscape, face-only, random object), respond:
   {"error":"no_garment","message":"Please upload a clear photo of a single clothing item."}

2) The image must show ONLY ONE garment/clothing item. If it shows a full outfit (top + bottom, layered pieces) or multiple items, respond:
   {"error":"multiple_items","message":"Please upload a photo where only ONE garment is visible (not a full outfit or multiple items)."}

3) If the garment is present but NOT suitable for trimming, pick the best matching error:
   - Too blurry / motion blur:
     {"error":"too_blurry","message":"The item photo is too blurry. Please retake with steady hands and good focus."}
   - Too dark / harsh shadows hiding edges:
     {"error":"too_dark","message":"The item photo is too dark. Please retake in brighter, even lighting so edges are visible."}
   - Garment is too small in frame / far away:
     {"error":"too_small","message":"The item is too small in the photo. Please move closer so the garment fills most of the frame."}
   - Garment is cropped / not fully visible (sleeves/hem/collar missing):
     {"error":"cropped_item","message":"Please upload a photo where the entire garment is visible (no cropped sleeves/hem/collar)."}
   - Busy background makes edges hard:
     {"error":"busy_background","message":"Background is too busy. Please place the item on a plain background for clean trimming."}
   - Item is heavily occluded (hands/bag/hair/coat covering it) or folded:
     {"error":"occluded_item","message":"The item is partially covered or folded. Please retake with the full garment laid flat or fully visible."}
   - Multiple clothing items overlap or there are multiple garments:
     {"error":"multiple_items","message":"Please upload a photo where only ONE garment is visible (no overlapping garments)."}

4) If the image is suitable for trimming, respond:
   {"ok": true}

Important:
- If the garment is being worn, it must be the ONLY visible garment/clothing item in the image.
- The full garment must be visible (including sleeves and hem) for accurate trimming."""

    try:
        response = ollama.chat(
            model=settings.VISION_MODEL,
            options={"num_ctx": 512, "num_predict": 120, "temperature": 0.0},
            messages=[{"role": "user", "content": prompt, "images": [image_data]}],
        )
    except Exception as e:
        return {"error": "analysis_failed", "message": str(e)}

    parsed = _parse_json(response["message"]["content"])
    if parsed.get("ok") is True:
        return {"ok": True}
    if parsed.get("error") and parsed.get("message"):
        return {"error": parsed["error"], "message": parsed["message"]}
    return {"error": "invalid_response", "message": "Could not validate item photo."}


def validate_user_photo_for_outfit_fit(image_path: str) -> Dict[str, Any]:
    """
    Validate Step 2 user photo quality for fit/try-on context.

    Returns:
      - {"ok": True}
      - {"error": "<code>", "message": "<user-facing>"} where code is one of:
        "no_person", "not_full_body", "face_not_visible", "too_blurry", "too_dark",
        "heavy_outerwear", "pose_issue", "invalid_response"
    """
    image_data = _encode_image(image_path)
    prompt = """You are validating a user's full-body photo for a virtual styling app.
Answer with ONLY a JSON object, nothing else.

Requirements:
- A PERSON must be clearly visible.
- FULL BODY must be visible: head to toe, with body outline visible.
- Face should be visible (not required to be close-up, but visible enough to confirm person).
- Lighting should be even, not too dark.
- The person should NOT be wearing a coat, puffer, heavy winter jacket, cape, or bulky layers that hide body structure.
- Pose: standing straight, arms relaxed, minimal occlusion (no big bag covering torso).

If any requirement fails, return the best matching error JSON:
{"error":"no_person","message":"No person detected. Please upload a full-body photo of yourself."}
{"error":"not_full_body","message":"Please upload a head-to-toe full-body photo for best results."}
{"error":"face_not_visible","message":"Please upload a photo where your face is visible (not covered by a phone/hat/mask)."}
{"error":"too_blurry","message":"The photo is too blurry. Please retake with better focus."}
{"error":"too_dark","message":"The photo is too dark. Please retake in brighter lighting."}
{"error":"heavy_outerwear","message":"Please remove coats/heavy winter layers so your body structure is visible (e.g., no puffer jackets)."}
{"error":"pose_issue","message":"Please stand straight with arms relaxed and avoid covering your torso (no big bags)."}

If all requirements pass, return:
{"ok": true}"""

    try:
        response = ollama.chat(
            model=settings.VISION_MODEL,
            options={"num_ctx": 512, "num_predict": 120, "temperature": 0.0},
            messages=[{"role": "user", "content": prompt, "images": [image_data]}],
        )
    except Exception as e:
        return {"error": "analysis_failed", "message": str(e)}

    parsed = _parse_json(response["message"]["content"])
    if parsed.get("ok") is True:
        return {"ok": True}
    if parsed.get("error") and parsed.get("message"):
        return {"error": parsed["error"], "message": parsed["message"]}
    return {"error": "invalid_response", "message": "Could not validate full-body photo."}

