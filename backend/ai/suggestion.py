"""LLM-based outfit suggestion engine with RAG context."""

import json
import re
import time
from functools import lru_cache

import ollama

from core.config import settings
from ai.retriever import load_outfit_db, retrieve_similar_outfits, format_for_prompt

FASHION_SYSTEM_PROMPT = """You are an expert personal stylist. Suggest complete outfits for a given clothing item.
Always respond in valid JSON only. No extra text.

BANNED ITEMS (NEVER suggest):
- Skinny/slim-fit/tapered jeans or pants → use straight-leg, wide-leg, baggy, relaxed, or barrel only
- Stiletto heels → use block heels, mules, loafers
- Platform flip-flops, Ugg boots (non-loungewear), bodycon dresses, peplum tops, wedge sneakers, fedora hats

STRICT RULES (DO NOT VIOLATE):
1. NAVY LIMIT: Max 1 navy item per outfit. Navy ≠ black. If anchor is black/dark, use black/charcoal — not navy.
2. STYLE COHERENCE: All items in one outfit must share the same style register.
   - Casual → jeans/casual trousers + casual top + sneakers/loafers + casual bag
   - Smart-casual → tailored trousers + neat top + loafers/clean sneakers + structured bag
   - Business casual → tailored trousers/skirt + blouse/shirt + heels/loafers + structured bag
   - Date night → elevated pieces only — no gym shoes, no hoodies
   - Do NOT mix athletic with tailored, or summer-casual with formal.
3. SEASON: All items must match the anchor item's season. No summer sandals with fall coats.
4. BOTTOMS FIT: ONLY straight-leg, wide-leg, baggy, relaxed, or barrel. NEVER skinny/slim/tapered/fitted.
5. GENDER TOPS — Men: shirt/polo/tee/henley/sweater/knit/sweatshirt only. NEVER blouse.
   Women: blouse/top/shirt/tee/sweater/tunic as appropriate."""


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

    # Slim attributes: only fields the LLM needs (drops material_guess, tags, etc.)
    _SLIM_FIELDS = {"item_type", "category", "color", "pattern", "style_category", "season", "gender", "age_group", "fit"}
    slim_attrs = {k: v for k, v in item_attributes.items() if k in _SLIM_FIELDS and v}

    user_context = ""
    if user_appearance and not user_appearance.get("error"):
        _UP_FIELDS = {"skin_tone", "undertone", "hairstyle", "body_type", "gender"}
        slim_appearance = {k: v for k, v in user_appearance.items() if k in _UP_FIELDS and v}
        user_context = (
            f"\nUSER: {json.dumps(slim_appearance, separators=(',', ':'))}"
            "\n- Match colors to skin tone/undertone. Consider hairstyle for accessories/necklines."
        )

    # Build required items: everything EXCEPT the anchor's category
    required_categories = []
    if anchor_category != "top":
        top_ex = "shirt/polo/tee/sweater" if gender == "men" else "blouse/top/shirt/sweater"
        required_categories.append(f'1 top (category="top", e.g. {top_ex})')
    if anchor_category != "bottom":
        required_categories.append('1 bottom (category="bottom", e.g. pants/skirt/shorts)')
    if anchor_category != "shoes":
        required_categories.append('1 shoes (category="shoes")')
    if anchor_category != "accessory":
        required_categories.append('1–4 accessories (category="accessory": bag/jewelry/belt/hat; max 1 bag, max 1 belt; scarves only in cold weather)')
    if anchor_category != "outerwear":
        required_categories.append(f'Optional outerwear (category="outerwear") only if {season} weather requires it')
    required_bullets = "\n* ".join(required_categories)
    min_items = max(3, len([c for c in ["top", "bottom", "shoes"] if c != anchor_category]) + 1)

    prompt = f"""Item: {json.dumps(slim_attrs, separators=(',', ':'))}
{user_context}

User: {age_group} {gender}. Occasions: {', '.join(occasions)}. Season: {season}.

RULES:
- Anchor category="{anchor_category}" is already owned — NEVER suggest another "{anchor_category}".
- Generate 1 outfit per occasion. Each outfit: {min_items}–6 items from these categories only:
* {required_bullets}
- Each item must have: category, type, color, description, enrichment, shopping_keywords.

Respond ONLY with this JSON:
{{"anchor_item":"<type+color>","gender_context":"{gender}","age_group":"{age_group}","outfits":[{{"occasion":"<name>","style_title":"<title>","items":[{{"category":"<cat>","type":"<type>","color":"<color>","description":"<desc>","enrichment":"<why>","shopping_keywords":"<keywords>"}}],"style_notes":"<notes>","color_palette":["<c1>","<c2>","<c3>"]}}]}}"""

    print(f"[TIMER] RAG + prompt build: {time.time() - start:.4f}s")

    start = time.time()
    response = ollama.chat(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": FASHION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": 0.7, "num_predict": 1200, "num_ctx": 4096},
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
