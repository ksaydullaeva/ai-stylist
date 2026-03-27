"""
Optional user-appearance analysis for context-aware outfit recommendations.
Extracts skin tone, hairstyle, and other visible attributes from a selfie.
"""

from typing import Any, Dict

from ai.gemini_client import extract_json_obj, generate_vision_text
from core.config import settings


def analyze_user_appearance(image_path: str) -> Dict[str, Any]:
    """
    Analyze a selfie for styling context.
    Returns a dict with skin_tone, undertone, hairstyle, hair_color, face_shape, general_notes.
    If no person is detected, returns {"error": "no_person", "message": "..."}.
    """
    prompt = """You are a fashion and style expert. Look at this image and decide if it shows a PERSON (face/portrait/selfie or full body).
If the image does NOT show a person (e.g. only clothing, object, landscape, or no clear face), respond with ONLY this JSON and nothing else:
{"error": "no_person", "message": "No person detected. This feature works best with a photo of yourself."}

If the image DOES show a person, analyze their appearance for styling recommendations. Extract:
- gender: if the person's presentation is clearly masculine or feminine, use exactly "men" or "women"; otherwise omit (do not guess)
- skin_tone: one of "fair", "light", "medium", "olive", "tan", "brown", "dark" or a short phrase (e.g. "warm medium")
- undertone: "cool", "warm", or "neutral" if visible
- hairstyle: brief description (e.g. "short dark hair", "long wavy blonde", "curly black")
- hair_color: if clearly visible
- body_type: f.e Hourglass, Pear (Triangle), Apple (Inverted Triangle), Rectangle (Straight), Spoon (Diamond)
- face_shape: only if clearly visible: "oval", "round", "square", "heart", "oblong" or skip
- general_notes: one short sentence of styling-relevant notes (e.g. "glasses, casual setting")

Respond ONLY with a valid JSON object. No markdown, no extra text."""

    try:
        raw_text = generate_vision_text(
            prompt,
            image_path=image_path,
            model_name=settings.VISION_MODEL,
            temperature=0.0,
            max_output_tokens=600,
            max_image_size=400,
        )
    except Exception as e:
        return {"error": "analysis_failed", "message": str(e)}

    parsed = extract_json_obj(raw_text)  # expects a JSON object
    if parsed is None:
        return {} if "{" not in raw_text else {"raw_output": raw_text}

    if parsed.get("error") == "no_person":
        return parsed

    return {k: v for k, v in parsed.items() if k not in ("error", "message") and v is not None}


def validate_user_photo_for_tryon(image_path: str) -> Dict[str, Any]:
    """
    Check that the image shows a person and full body (for virtual try-on).
    Returns {"ok": True} or {"error": "no_person"|"not_full_body", "message": "..."}.
    """
    prompt = """Look at this image. Answer with ONLY a JSON object, nothing else.

1. Does it show a PERSON (human face/body)? If NO (e.g. object, landscape, animal, only clothing), respond:
   {"error": "no_person", "message": "No person detected. Please upload a photo of yourself."}

2. Does it show the person's FULL BODY (at least from chest/mid-torso down to knees or feet, or head to toe)? If it shows only face, head, bust, or upper body only, respond:
   {"error": "not_full_body", "message": "Please upload a full-body photo for best try-on results."}

3. If it shows a person with full body visible, respond:
   {"ok": true}"""

    try:
        raw_text = generate_vision_text(
            prompt,
            image_path=image_path,
            model_name=settings.VISION_MODEL,
            temperature=0.0,
            max_output_tokens=300,
            max_image_size=420,
        )
    except Exception as e:
        return {"error": "analysis_failed", "message": str(e)}

    parsed = extract_json_obj(raw_text)
    if parsed is None:
        return {"error": "invalid_response", "message": "Could not validate image."}

    if parsed.get("ok") is True:
        return {"ok": True}

    if parsed.get("error") and parsed.get("message"):
        return {"error": parsed["error"], "message": parsed["message"]}

    return {"error": "invalid_response", "message": "Please upload a clear full-body photo."}
