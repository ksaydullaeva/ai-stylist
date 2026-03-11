"""
Demo endpoint: load test outfits and placeholder images without calling Gemini.
Use for testing the lookbook, try-on flow, and past lookbooks without using API tokens.
"""

import io
import uuid
from pathlib import Path

from fastapi import APIRouter

from core.config import settings
from repositories.outfit import persist_outfits
from services.pipeline import OUTPUT_DIR, UPLOAD_DIR, attach_image_urls

router = APIRouter(tags=["demo"])

# Test outfit data: same shape as AI suggestion output, no image_url until we attach
DEMO_OUTFIT_DATA = {
    "anchor_item": "denim jacket",
    "gender_context": "unisex",
    "age_group": "adult",
    "outfits": [
        {
            "occasion": "Casual",
            "style_title": "Cool & Casual",
            "style_notes": "Relaxed weekend look that pairs your jacket with easy separates.",
            "color_palette": ["navy", "white", "denim blue"],
            "items": [
                {
                    "category": "top",
                    "type": "t-shirt",
                    "color": "white",
                    "description": "Basic white tee",
                    "enrichment": "Clean base that lets the jacket stand out.",
                    "shopping_keywords": "white crew neck t-shirt",
                },
                {
                    "category": "bottom",
                    "type": "jeans",
                    "color": "navy blue",
                    "description": "Straight leg jeans",
                    "enrichment": "Pairs well with the jacket and adds a touch of casual chic.",
                    "shopping_keywords": "navy straight leg jeans",
                },
                {
                    "category": "shoes",
                    "type": "sneakers",
                    "color": "white",
                    "description": "White sneakers",
                    "enrichment": "Adds a sporty vibe to the look.",
                    "shopping_keywords": "white sneakers",
                },
                {
                    "category": "accessory",
                    "type": "tote bag",
                    "color": "white",
                    "description": "Canvas tote",
                    "enrichment": "Adds a touch of simplicity and function.",
                    "shopping_keywords": "white canvas tote bag",
                },
            ],
        },
        {
            "occasion": "Smart casual",
            "style_title": "Polished casual",
            "style_notes": "Elevated casual with structured pieces.",
            "color_palette": ["denim", "black", "white"],
            "items": [
                {
                    "category": "top",
                    "type": "oxford shirt",
                    "color": "white",
                    "description": "Classic oxford",
                    "enrichment": "Layers neatly under the jacket.",
                    "shopping_keywords": "white oxford shirt",
                },
                {
                    "category": "bottom",
                    "type": "chinos",
                    "color": "black",
                    "description": "Slim chinos",
                    "enrichment": "Smart-casual balance with the denim.",
                    "shopping_keywords": "black chinos",
                },
                {
                    "category": "shoes",
                    "type": "loafers",
                    "color": "brown",
                    "description": "Leather loafers",
                    "enrichment": "Dresses up the outfit without going formal.",
                    "shopping_keywords": "brown leather loafers",
                },
                {
                    "category": "accessory",
                    "type": "belt",
                    "color": "brown",
                    "description": "Leather belt",
                    "enrichment": "Ties the look together.",
                    "shopping_keywords": "brown leather belt",
                },
            ],
        },
    ],
}


def _create_placeholder_jpeg(size: int = 400, text: str = "") -> bytes:
    """Create a small placeholder image as JPEG bytes with optional text."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return b""
    
    # Use a slightly more vibrant but still soft color
    img = Image.new("RGB", (size, size), color=(245, 245, 250))
    
    if text:
        draw = ImageDraw.Draw(img)
        # Try to center the text
        # Since we might not have a font file, we'll use the default font
        try:
            # draw.text((x, y), text, fill=color)
            # Default font is tiny, but it's better than nothing
            draw.text((10, size // 2), text.upper(), fill=(100, 100, 120))
        except Exception:
            pass
            
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _build_demo_result():
    """
    Create placeholder images on disk, persist demo outfits to DB, return pipeline-shaped result.
    Does not call Gemini or any AI.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    placeholder_bytes = _create_placeholder_jpeg()
    if not placeholder_bytes:
        raise RuntimeError("PIL required for demo placeholder images")

    # Demo "source" image in OUTPUT_DIR so /api/v1/images/ can serve it for preview
    demo_source_name = f"demo_source_{uuid.uuid4().hex[:8]}.jpg"
    demo_source_path = OUTPUT_DIR / demo_source_name
    demo_source_path.write_bytes(placeholder_bytes)

    outfits = list(DEMO_OUTFIT_DATA["outfits"])
    image_results = []

    for outfit in outfits:
        paths = []
        for item in outfit.get("items", []):
            item_type = item.get("type") or "item"
            safe_type = item_type.replace(" ", "_")[:30]
            filename = f"item_demo_{uuid.uuid4().hex[:6]}_{safe_type}.jpg"
            path = OUTPUT_DIR / filename
            
            # Create placeholder with text
            placeholder_bytes = _create_placeholder_jpeg(text=item_type)
            path.write_bytes(placeholder_bytes)
            paths.append(str(path))
        image_results.append({"individual_items": paths})

    attach_image_urls(outfits, image_results)
    outfit_ids = persist_outfits(
        outfits,
        image_results,
        demo_source_path,
        {"style_category": "casual", "demo": True},
    )
    for i, o in enumerate(outfits):
        if i < len(outfit_ids):
            o["id"] = outfit_ids[i]

    return {
        "success": True,
        "image_id": f"/outputs/{demo_source_name}",
        "attributes": {"style_category": "casual", "demo": True},
        "outfits": {
            "anchor_item": DEMO_OUTFIT_DATA["anchor_item"],
            "gender_context": DEMO_OUTFIT_DATA["gender_context"],
            "age_group": DEMO_OUTFIT_DATA["age_group"],
            "outfits": outfits,
        },
    }


@router.post("/load-demo")
def load_demo():
    """
    Load test outfits with placeholder images and persist to DB.
    Returns the same shape as the full-pipeline result so the frontend can show the lookbook.
    No Gemini or AI is called; use this to test the flow without using tokens.
    """
    try:
        data = _build_demo_result()
        return data
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e)) from e
