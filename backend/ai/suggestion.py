"""LLM-based outfit suggestion engine with RAG context."""

import json
import re
import time
from functools import lru_cache

import ollama

from core.config import settings
from ai.retriever import load_outfit_db, retrieve_similar_outfits, format_for_prompt

FASHION_SYSTEM_PROMPT = """You are an expert personal stylist with deep knowledge of:
- Color theory and complementary palettes
- Occasion-appropriate dressing (work, casual, formal, date night)
- Fit and proportion balancing
- Seasonal appropriateness
- Current style trends

When given a clothing item's attributes, suggest complete outfits.
Always respond in valid JSON only. No extra text."""

BANNED_ITEMS = """
NEVER suggest these outdated items under any circumstances:
- Skinny jeans (suggest straight leg, wide leg, or barrel fit instead)
- Stiletto heels (suggest block heels, mules, or loafers instead)
- Platform flip flops
- Ugg boots (unless specifically loungewear)
- Cargo pants with excessive pockets
- Bodycon dresses
- Peplum tops
- Wedge sneakers
- Over-the-knee socks as fashion
- Fedora hats

ALWAYS prefer modern alternatives:
- Jeans: straight leg, wide leg, barrel, baggy, mom jeans
- Shoes: loafers, mules, mary janes, chunky sneakers, kitten heels, ballet flats
- Bags: shoulder bags, tote bags, mini bags
"""

VALID_CATEGORIES = {"top", "bottom", "shoes", "accessory", "outerwear"}

# Keywords to infer category from item_type when vision model doesn't return category
CATEGORY_INFER_KEYWORDS = {
    "top": ("shirt", "blouse", "top", "tee", "tank", "sweater", "hoodie", "cardigan", "tunic", "crop", "turtleneck", "dress", "jumpsuit", "romper"),
    "bottom": ("pants", "trousers", "jeans", "skirt", "shorts", "leggings", "joggers"),
    "shoes": ("shoes", "sneakers", "boots", "sandals", "loafers", "heels", "flats", "mules", "pumps", "oxfords"),
    "accessory": ("bag", "belt", "hat", "scarf", "watch", "jewelry", "necklace", "bracelet", "earrings", "sunglasses"),
    "outerwear": ("jacket", "coat", "blazer", "vest", "parka", "trench", "bomber"),
}


def _infer_anchor_category(item_attributes: dict) -> str:
    """Infer the uploaded item's category (top/bottom/shoes/accessory/outerwear)."""
    raw = item_attributes.get("category")
    if isinstance(raw, str) and raw.strip().lower() in VALID_CATEGORIES:
        return raw.strip().lower()
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, str) and c.strip().lower() in VALID_CATEGORIES:
                return c.strip().lower()
    item_type = (item_attributes.get("item_type") or "").lower()
    if not item_type:
        return "top"  # safe default so we still suggest bottoms/shoes/etc.
    for category, keywords in CATEGORY_INFER_KEYWORDS.items():
        if any(kw in item_type for kw in keywords):
            return category
    return "top"


@lru_cache(maxsize=1)
def _get_outfit_db() -> list:
    """Load the RAG dataset once and cache it."""
    return load_outfit_db(str(settings.POLYVORE_JSON))


def generate_outfit_suggestions(
    item_attributes: dict,
    occasions: list[str] | None = None,
    user_appearance: dict | None = None,
) -> dict:
    """Generate complete outfit suggestions for a garment.

    Args:
        item_attributes: Structured dict from analyze_wardrobe_item().
        occasions: List of occasion strings; auto-detected if None.
        user_appearance: Optional dict from analyze_user_appearance() for personalisation.
    """
    if occasions is None:
        occasions = ["casual", "smart-casual", "formal"]

    gender = item_attributes.get("gender", "unisex")
    age_group = item_attributes.get("age_group", "adult")
    season = item_attributes.get("season", "all-season")
    anchor_category = _infer_anchor_category(item_attributes)

    start = time.time()
    similar = retrieve_similar_outfits(item_attributes, _get_outfit_db(), top_k=3)
    rag_context = format_for_prompt(similar)  # noqa: F841 — available for prompt expansion

    user_context = ""
    if user_appearance and not user_appearance.get("error"):
        user_context = f"""
    CONTEXT FROM USER'S PHOTO (use to personalise colors and style):
    {json.dumps(user_appearance, indent=2)}
    - Suggest colors that complement their skin tone and undertone.
    - Consider their hairstyle and overall look when choosing accessories and necklines.
    """

    # Build required items: everything EXCEPT the anchor's category (user already has that)
    required_categories = []
    if anchor_category != "top":
        required_categories.append('Exactly 1 top (category="top", e.g. shirt, blouse, sweater — not outerwear)')
    if anchor_category != "bottom":
        required_categories.append('Exactly 1 bottom (category="bottom", e.g. pants, skirt, shorts)')
    if anchor_category != "shoes":
        required_categories.append('Exactly 1 pair of shoes (category="shoes")')
    if anchor_category != "accessory":
        required_categories.append('At least 1 and up to 2 accessories (category="accessory", e.g. bag, belt, jewelry, scarf, hat)')
    if anchor_category != "outerwear":
        required_categories.append(f'Optional outerwear (category="outerwear") ONLY if season is {season} and weather requires it')
    required_bullets = "\n        * ".join(required_categories)
    min_items = max(3, len([c for c in ["top", "bottom", "shoes"] if c != anchor_category]) + 1)  # at least 3 complements + optional accessory/outerwear

    prompt = f"""Here is a clothing item from the user's wardrobe:

    {json.dumps(item_attributes, indent=2)}
    {user_context}

    ANCHOR CATEGORY RULE (CRITICAL — DO NOT VIOLATE):
    - The user's uploaded item is a "{anchor_category}". They already have this piece.
    - Do NOT suggest ANY item with category="{anchor_category}" in the "items" list. Suggest only items that PAIR WITH the user's item (e.g. if they uploaded pants, suggest tops, shoes, accessories — never more pants).

    The user is a {age_group} {gender} person. Generate outfit suggestions accordingly.
    All suggested items must be appropriate for {gender} {age_group} style.

    Occasions to cover: {', '.join(occasions)}.

    SEASON RULES (STRICT — ALL ITEMS MUST MATCH THE SAME SEASON):
    - The user's item is for: {season}. Every suggested item (top, bottom, shoes, accessory, outerwear) MUST be appropriate for that same season.
    - Do NOT mix summer-only items (e.g. slide sandals, flip-flops, open-toe sandals) with fall/winter items (e.g. heavy jackets, scarves, boots).
    - Do NOT mix winter-only items (e.g. heavy coats, warm scarves, boots) with summer items (e.g. sandals, tank tops).
    - Shoes and accessories must match the season: e.g. for fall/winter use boots, loafers, closed-toe shoes; for summer use sandals, espadrilles; for all-season use versatile options.

    STRUCTURE RULES (STRICT — DO NOT VIOLATE):
    - Every outfit MUST include, in its "items" list, ONLY complementary categories (never the same type as the user's item):
        * {required_bullets}
    - Do NOT include any item with category="{anchor_category}" — the user's uploaded item fills that role.
    - Each entry in "items" MUST be a separate object, never merged.
    - The "items" array MUST contain at least {min_items} and at most 6 objects.
    - For each item, include "enrichment": a short, catchy sentence explaining why this piece enriches the look.

    BANNED ITEMS (STRICT — DO NOT VIOLATE):
    {BANNED_ITEMS}

    Respond ONLY with this JSON structure:
    {{
    "anchor_item": "<item type and color>",
    "gender_context": "{gender}",
    "age_group": "{age_group}",
    "outfits": [
        {{
        "occasion": "<occasion name>",
        "style_title": "<catchy outfit name>",
        "items": [
            {{
            "category": "top" | "bottom" | "shoes" | "accessory" | "outerwear",
            "type": "<item type>",
            "color": "<recommended color>",
            "description": "<brief description>",
            "enrichment": "<one catchy sentence why this item enriches the look>",
            "shopping_keywords": "<gender-specific search keywords e.g. 'women slim fit trousers black'>"
            }}
        ],
        "style_notes": "<why this outfit works>",
        "color_palette": ["<color1>", "<color2>", "<color3>"]
        }}
    ]
    }}"""

    print(f"[TIMER] RAG + prompt build: {time.time() - start:.4f}s")

    start = time.time()
    response = ollama.chat(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": FASHION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": 0.7, "num_predict": 1200, "num_ctx": 2048},
    )
    print(f"[TIMER] ollama.chat: {time.time() - start:.4f}s")

    raw_text = response["message"]["content"]
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        parsed = json.loads(match.group())
        # Enforce: remove any suggested item with same category as the user's (anchor) item
        for outfit in parsed.get("outfits", []):
            items = outfit.get("items") or []
            outfit["items"] = [it for it in items if (it.get("category") or "").strip().lower() != anchor_category]
        _log_outfit_summary(parsed)
        return parsed

    return {"raw": raw_text}


def _log_outfit_summary(outfit_data: dict) -> None:
    """Log a compact outfit summary for debugging."""
    print(f"\n Anchor: {outfit_data.get('anchor_item')}")
    for outfit in outfit_data.get("outfits", []):
        print(f"  [{outfit.get('occasion')}] {outfit.get('style_title')}")


if __name__ == "__main__":
    from ai.captioning import analyze_wardrobe_item
    from research.image_generator import OutfitImageGenerator

    image = "examples/navy-blue-jacket.png"
    item = analyze_wardrobe_item(image)
    result = generate_outfit_suggestions(item_attributes=item, occasions=[item["style_category"]])

    generator = OutfitImageGenerator()
    for idx in range(len(result.get("outfits", []))):
        generator.generate_full_suite(result, outfit_index=idx, output_dir="outfit_previews", source_image_path=image)
