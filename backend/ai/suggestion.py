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
- Skinny jeans, slim-fit jeans, tapered jeans, slim-fit pants, tapered pants (STRICTLY use straight leg, wide leg, barrel, baggy, or relaxed fit instead)
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

PREFERENCES_BOTTOMS_AND_COLOR = """
STRONG PREFERENCES (apply when suggesting items):
- Bottoms (pants, trousers, jeans): You MUST use only straight-leg, wide-leg, baggy, relaxed fit, or barrel leg. NEVER use "skinny", "slim-fit", "slim fit", "tapered", or "fitted" for pants/jeans/trousers. Always write the type and description with "straight leg", "wide leg", "baggy", "relaxed fit", or "barrel leg".
- Navy blue vs black: Do NOT overuse navy blue. Navy and black are different: navy has a blue undertone. If the user's item is black or very dark, suggest true black, charcoal, or other dark neutrals rather than defaulting to navy. Suggest navy only when it is a clear, intentional choice (e.g. navy blazer, nautical look), not as a substitute for black. Vary colors across outfits — avoid suggesting navy for multiple items (e.g. navy pants + navy boots) unless it is a deliberate monochrome navy look.
- Gender-appropriate tops: For MEN, use ONLY masculine top terms: "shirt", "polo", "tee", "henley", "sweater", "knit", "sweatshirt", "oxford shirt". NEVER suggest "blouse" for men — blouse is for women only. For WOMEN, use "blouse", "top", "shirt", "tee", "sweater", "tunic" as appropriate. The "type" and "description" fields must use the correct term for the user's gender.
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

    # Prefer gender from user's photo when available; otherwise from garment attributes
    gender = "unisex"
    if user_appearance and not user_appearance.get("error"):
        g = (user_appearance.get("gender") or "").strip().lower()
        if g in ("men", "women"):
            gender = g
        elif g in ("male", "man"):
            gender = "men"
        elif g in ("female", "woman"):
            gender = "women"
    if gender == "unisex":
        g = (item_attributes.get("gender") or "").strip().lower()
        if g in ("men", "women"):
            gender = g
        elif g in ("male", "man"):
            gender = "men"
        elif g in ("female", "woman"):
            gender = "women"
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
        if gender == "men":
            required_categories.append('Exactly 1 top (category="top", e.g. shirt, polo, tee, sweater — NEVER blouse; not outerwear)')
        else:
            required_categories.append('Exactly 1 top (category="top", e.g. shirt, blouse, sweater — not outerwear)')
    if anchor_category != "bottom":
        required_categories.append('Exactly 1 bottom (category="bottom", e.g. pants, skirt, shorts)')
    if anchor_category != "shoes":
        required_categories.append('Exactly 1 pair of shoes (category="shoes")')
    if anchor_category != "accessory":
        required_categories.append(
            'At least 2 and up to 4 accessories (category="accessory", e.g. bag, jewelry, belt, hat). '
            'Do not suggest more than 1 bag or more than 1 belt per outfit. '
            'Vary accessory types; suggest scarves only when seasonally appropriate (e.g. cold weather), not in every outfit. '
            'Prefer bags, belts, or jewelry when they fit the look; do not default to scarves for every look.'
        )
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
    CRITICAL for men: Do NOT recommend a blouse. For tops, use only: shirt, polo, tee, henley, sweater, knit, sweatshirt, oxford shirt.
    CRITICAL for bottoms: Do NOT recommend skinny, slim-fit, or tapered jeans/pants. Use ONLY: straight leg, wide leg, baggy, relaxed fit, barrel leg. The "type" and "description" for any bottom must include one of these fit terms.

    Occasions to cover: {', '.join(occasions)}.

    SEASON RULES (STRICT — ALL ITEMS MUST MATCH THE SAME SEASON):
    - The user's item is for: {season}. Every suggested item (top, bottom, shoes, accessory, outerwear) MUST be appropriate for that same season.
    - Do NOT mix summer-only items (e.g. slide sandals, flip-flops, open-toe sandals) with fall/winter items (e.g. heavy jackets, scarves, boots).
    - Do NOT mix winter-only items (e.g. heavy coats, warm scarves, boots) with summer items (e.g. sandals, tank tops).
    - Shoes and accessories must match the season: e.g. for fall/winter use boots, loafers, closed-toe shoes; for summer use sandals, espadrilles; for all-season use versatile options.

    WEATHER PROFILE (REQUIRED):
    Before giving outfit suggestions, internally assume ONE weather profile:
    - warm weather outfit
    - mild weather outfit
    - cold weather outfit
    All items must match that weather profile.

    STRUCTURE RULES (STRICT — DO NOT VIOLATE):
    - Every outfit MUST include, in its "items" list, ONLY complementary categories (never the same type as the user's item):
        * {required_bullets}
    - Do NOT include any item with category="{anchor_category}" — the user's uploaded item fills that role.
    - At most 1 bag and at most 1 belt per outfit; do not suggest multiple bags or multiple belts.
    - Each entry in "items" MUST be a separate object, never merged.
    - The "items" array MUST contain at least {min_items} and at most 6 objects.
    - For each item, include "enrichment": a short, catchy sentence explaining why this piece enriches the look.

    PREFERENCES (STRONG — APPLY WHEN SUGGESTING):
    {PREFERENCES_BOTTOMS_AND_COLOR}

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
            "shopping_keywords": "<gender-specific search keywords e.g. 'women trousers black'>"
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
        # Enforce: no blouse for men — replace with shirt in type/description/shopping_keywords
        if gender == "men":
            for outfit in parsed.get("outfits", []):
                for it in outfit.get("items") or []:
                    if (it.get("category") or "").strip().lower() == "top":
                        for key in ("type", "description", "shopping_keywords"):
                            val = it.get(key)
                            if isinstance(val, str) and "blouse" in val.lower():
                                it[key] = re.sub(r"\bblouse\b", "shirt", val, flags=re.IGNORECASE)
        # Enforce: no skinny/slim/tapered bottoms — replace with straight leg or relaxed fit
        _enforce_straight_or_baggy_bottoms(parsed)
        _log_outfit_summary(parsed)
        return parsed

    return {"raw": raw_text}


# Terms we never want for bottoms; map to preferred fit
_BOTTOM_FIT_REPLACEMENTS = [
    (re.compile(r"\bskinny\b", re.IGNORECASE), "straight leg"),
    (re.compile(r"\bslim-fit\b", re.IGNORECASE), "straight leg"),
    (re.compile(r"\bslim fit\b", re.IGNORECASE), "straight leg"),
    (re.compile(r"\btapered\b", re.IGNORECASE), "straight leg"),
    (re.compile(r"\bfitted\s+(pants|jeans|trousers)\b", re.IGNORECASE), r"straight leg \1"),
    (re.compile(r"\bslim\s+(pants|jeans|trousers)\b", re.IGNORECASE), r"straight leg \1"),
    (re.compile(r"\b(classic\s+and\s+)?classic\s+fit\b", re.IGNORECASE), "straight leg fit"),
]


def _enforce_straight_or_baggy_bottoms(parsed: dict) -> None:
    """Rewrite any bottom item that mentions skinny/slim/tapered to use straight leg or relaxed fit."""
    allowed_fit = ("straight leg", "wide leg", "baggy", "relaxed fit", "barrel", "relaxed")
    for outfit in parsed.get("outfits", []):
        for it in outfit.get("items") or []:
            if (it.get("category") or "").strip().lower() != "bottom":
                continue
            for key in ("type", "description", "shopping_keywords"):
                val = it.get(key)
                if not isinstance(val, str):
                    continue
                original = val
                for pattern, repl in _BOTTOM_FIT_REPLACEMENTS:
                    val = pattern.sub(repl, val)
                if val != original:
                    it[key] = val
            # If type still has no allowed fit term, prepend "straight leg " to type
            t = (it.get("type") or "").strip()
            if t and not any(f in t.lower() for f in allowed_fit):
                it["type"] = "straight leg " + t.lstrip()


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
