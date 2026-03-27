"""LLM-based outfit suggestion engine with RAG context."""

import json
import re
import random
import time
from functools import lru_cache
from pathlib import Path

from core.config import settings
from ai.retriever import load_outfit_db, retrieve_similar_outfits, format_for_prompt
from ai.gemini_client import extract_json_obj, generate_text

# ---------------------------------------------------------------------------
# Trend context — loaded once from current_brands.json at import time.
# Refresh the JSON each season to keep suggestions grounded in current style.
# ---------------------------------------------------------------------------
_TREND_FILE = Path(__file__).parent / "current_brands.json"

@lru_cache(maxsize=1)
def _load_trend_data() -> dict:
    try:
        return json.loads(_TREND_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[trends] failed to load {_TREND_FILE}: {exc}")
        return {}


def _build_trend_snippet(gender: str, exclude_category: str | set = "") -> str:
    """Return a compact trend context string for the given gender.

    Items belonging to any category in `exclude_category` are stripped so the
    trend context never nudges the LLM to suggest something the user already owns.
    `exclude_category` may be a single category string or a set of strings.
    """
    data = _load_trend_data()
    if not data:
        return ""

    meta = data.get("_meta", {})
    season = meta.get("season", "current season")

    # Normalise exclude_category → set of category strings
    if isinstance(exclude_category, str):
        excl_cats = {exclude_category} if exclude_category else set()
    else:
        excl_cats = set(exclude_category)

    # Build the union of type keywords for all excluded categories
    exclude_kws: set[str] = set()
    for cat in excl_cats:
        exclude_kws.update(CATEGORY_INFER_KEYWORDS.get(cat, ()))

    sil_key = gender if gender in ("women", "men") else "unisex"
    silhouettes = data.get("silhouettes", {}).get(sil_key, [])
    unisex_sil = data.get("silhouettes", {}).get("unisex", [])
    all_sil = (silhouettes + unisex_sil)[:5]

    colors = data.get("color_palettes", {}).get("SS2026", [])[:7]
    fabrics = data.get("textures_and_fabrics", [])[:5]

    raw_trending = data.get("trending_items", {}).get(sil_key, [])
    trending = [
        t for t in raw_trending
        if not any(kw in t.lower() for kw in exclude_kws)
    ][:5]

    if exclude_kws:
        all_sil = [s for s in all_sil if not any(kw in s.lower() for kw in exclude_kws)]

    rules = data.get("styling_rules_SS2026", [])[:4]
    avoid = data.get("avoid_trends", [])[:3]

    lines = [
        f"TREND CONTEXT ({season}):",
        f"- Silhouettes: {', '.join(all_sil)}",
        f"- Colors: {', '.join(colors)}",
        f"- Fabrics: {', '.join(fabrics)}",
    ]
    if trending:
        lines.append(f"- Trending items: {', '.join(trending)}")
    lines += [
        f"- Style rules: {'; '.join(rules)}",
        f"- Avoid: {', '.join(avoid)}",
    ]
    return "\n".join(lines)

FASHION_SYSTEM_PROMPT = """You are an expert personal stylist.
Return JSON only (no markdown/code fences).

Hard constraints:
- No banned items: stiletto heels, platform shoes/sandals/boots/mules (any platform sole), wedge sneakers, Ugg boots (non-loungewear), bodycon dresses, peplum tops, fedora hats.
- Bottoms fit must be straight-leg, wide-leg, baggy, relaxed, or barrel (never skinny/slim/tapered/fitted).
- Max 1 navy item per outfit. Navy != black.
- Keep one consistent style register per outfit (casual, smart-casual, business casual, date night).
- Match season across all items.
- Men tops: shirt/polo/tee/henley/sweater/knit/sweatshirt (never blouse).

Season coherence (important):
- If shoes are summer-style flats (type/description contains "ballet", "mesh", or "flats"), then the main top must be lightweight.
  In that case, do NOT use heavy/warm tops like "sweater", "hoodie", "turtleneck", or generic "knit top".
  Prefer: "tee", "tank", "blouse", "shirt", "linen shirt", or "lightweight ribbed knit"."""


VALID_CATEGORIES = {"top", "bottom", "dress", "shoes", "accessory", "outerwear"}

# Keywords to infer category from item_type when vision model doesn't return a correct category.
CATEGORY_INFER_KEYWORDS = {
    # One-piece categories should not fall under "top".
    "top": ("shirt", "blouse", "top", "tee", "tank", "sweater", "hoodie", "cardigan", "tunic", "crop", "turtleneck"),
    # Broad list — includes cut/silhouette words the LLM uses instead of the garment noun
    "bottom": (
        "pants", "trousers", "jeans", "skirt", "shorts", "leggings", "joggers",
        "chinos", "chino", "culottes", "culotte", "palazzo", "capris", "capri",
        "wide-leg", "wide leg", "straight leg", "barrel leg", "barrel-leg",
        "flared leg", "flare leg", "bootcut", "boot-cut", "baggy leg",
        "denim bottom", "high-waist", "high waist",
    ),
    "shoes": ("shoes", "sneakers", "boots", "sandals", "loafers", "heels", "flats", "mules", "pumps", "oxfords"),
    "accessory": ("bag", "belt", "hat", "scarf", "watch", "jewelry", "necklace", "bracelet", "earrings", "sunglasses"),
    "outerwear": ("jacket", "coat", "blazer", "vest", "parka", "trench", "bomber"),
    "dress": ("dress", "midi dress", "mini dress", "maxi dress", "jumpsuit", "romper", "overall", "playsuit", "bodysuit"),
}

# Item types that cover both top AND bottom — never pair with another top or bottom.
_FULL_OUTFIT_TYPES = ("dress", "jumpsuit", "romper", "overall", "playsuit", "bodysuit")


def _trim_sentence(text: str, max_chars: int) -> str:
    s = " ".join((text or "").split())
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars].rstrip()
    # Prefer cutting on a word boundary.
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.-") + "..."


def _clamp_generated_text(parsed: dict) -> None:
    """Keep generated copy concise for UI readability."""
    for outfit in parsed.get("outfits", []):
        if not isinstance(outfit, dict):
            continue
        if isinstance(outfit.get("style_notes"), str):
            outfit["style_notes"] = _trim_sentence(outfit["style_notes"], 180)

        items = outfit.get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("description"), str):
                item["description"] = _trim_sentence(item["description"], 120)
            if isinstance(item.get("enrichment"), str):
                item["enrichment"] = _trim_sentence(item["enrichment"], 110)
            if isinstance(item.get("shopping_keywords"), str):
                item["shopping_keywords"] = _trim_sentence(item["shopping_keywords"], 90)


def _extract_json_string_field(raw_text: str, key: str) -> str | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', raw_text)
    return m.group(1).strip() if m else None


def _salvage_outfit_objects_from_raw(raw_text: str) -> list[dict]:
    """Best-effort extraction of complete outfit objects from possibly truncated JSON text."""
    text = re.sub(r"```json|```", "", raw_text).strip()
    key_idx = text.find('"outfits"')
    if key_idx == -1:
        return []
    arr_start = text.find("[", key_idx)
    if arr_start == -1:
        return []

    decoder = json.JSONDecoder()
    i = arr_start + 1
    outfits: list[dict] = []
    n = len(text)
    while i < n:
        while i < n and text[i] in " \r\n\t,":
            i += 1
        if i >= n or text[i] == "]":
            break
        try:
            obj, end = decoder.raw_decode(text, i)
        except Exception:
            break
        if isinstance(obj, dict):
            outfits.append(obj)
        i = end
    return outfits


def _infer_anchor_category(item_attributes: dict) -> str:
    """Infer the uploaded item's category (top/bottom/dress/shoes/accessory/outerwear)."""
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


def _get_excluded_categories(item_attributes: dict) -> set[str]:
    """Return the full set of categories that must not appear in suggestions.

    Dresses, jumpsuits, and rompers cover both top and bottom, so both are
    excluded — suggesting a skirt or trousers on top of a dress makes no sense.
    For all other items only the anchor's own category is excluded.
    """
    anchor = _infer_anchor_category(item_attributes)
    item_type = (item_attributes.get("item_type") or "").lower()
    if any(ft in item_type for ft in _FULL_OUTFIT_TYPES):
        return {"top", "bottom"}
    return {anchor}


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
    # Generate at most 2 outfits by sampling random occasions from the provided list.
    # Keep order stable after sampling for more predictable UX.
    unique_occasions = [o for o in dict.fromkeys(occasions) if isinstance(o, str) and o.strip()]
    if len(unique_occasions) > 2:
        occasions = sorted(random.sample(unique_occasions, 2), key=unique_occasions.index)
    else:
        occasions = unique_occasions

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
    excluded_categories = _get_excluded_categories(item_attributes)  # may be >1 for dresses

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

    # Build required items: everything EXCEPT excluded categories
    required_categories = []
    if "top" not in excluded_categories:
        top_ex = "shirt/polo/tee/sweater" if gender == "men" else "blouse/top/shirt/sweater"
        required_categories.append(f'1 top (category="top", e.g. {top_ex})')
    if "bottom" not in excluded_categories:
        required_categories.append('1 bottom (category="bottom", e.g. pants/skirt/shorts)')
    if "shoes" not in excluded_categories:
        required_categories.append('1 shoes (category="shoes", e.g. loafers/sneakers/sandals — flat or low heel only, no platforms)')
    if "accessory" not in excluded_categories:
        required_categories.append('1–4 accessories (category="accessory": bag/jewelry/belt/hat; max 1 bag, max 1 belt; scarves only in cold weather)')
    if "outerwear" not in excluded_categories:
        required_categories.append(f'Optional outerwear (category="outerwear") only if {season} weather requires it')
    required_bullets = "\n* ".join(required_categories)
    min_items = max(
        3,
        len([c for c in ["top", "bottom", "shoes"] if c not in excluded_categories]) + 1,
    )

    # Pass all excluded categories into trend snippet so none bleed back through trend context
    trend_snippet = _build_trend_snippet(gender, exclude_category=excluded_categories)
    trend_block = f"{trend_snippet}\n\n" if trend_snippet else ""

    # Build an explicit constraint listing every forbidden category + its concrete type names.
    _excl_type_examples = "; ".join(
        f'{cat}: {", ".join(CATEGORY_INFER_KEYWORDS.get(cat, ()))}'
        for cat in sorted(excluded_categories)
    )
    anchor_constraint = (
        f"ANCHOR item is already owned — NEVER suggest any item whose category OR type "
        f"belongs to: {', '.join(sorted(excluded_categories))}. "
        f"Forbidden types — {_excl_type_examples}."
    )

    prompt = (
        f'ITEM: {json.dumps(slim_attrs, separators=(",", ":"))}\n'
        f"{user_context}\n\n"
        f"{trend_block}"
        f"CONTEXT: age_group={age_group}, gender={gender}, season={season}, occasions={','.join(occasions)}.\n"
        f"{anchor_constraint}\n"
        f"Generate exactly 1 outfit per occasion ({len(occasions)} total, max 2).\n"
        f"Each outfit must have {min_items}-6 items using only:\n* {required_bullets}\n"
        "Each item must include: category, type, color, description, enrichment, shopping_keywords.\n"
        "Also include style_notes and color_palette (3 colors) per outfit.\n"
        "Keep all text concise: style_notes <= 180 chars; description <= 120; enrichment <= 110; shopping_keywords <= 90.\n\n"
        'Output schema: {"anchor_item":"<type+color>","gender_context":"<gender>","age_group":"<age_group>","outfits":[{"occasion":"<name>","style_title":"<title>","items":[{"category":"<cat>","type":"<type>","color":"<color>","description":"<desc>","enrichment":"<why>","shopping_keywords":"<keywords>"}],"style_notes":"<notes>","color_palette":["<c1>","<c2>","<c3>"]}]}\n'
    )

    print(f"[TIMER] RAG + prompt build: {time.time() - start:.4f}s")

    combined_prompt = f"{FASHION_SYSTEM_PROMPT}\n\n{prompt}"
    start = time.time()
    raw_text = generate_text(
        combined_prompt,
        model_name=settings.LLM_MODEL,
        temperature=0.7,
        max_output_tokens=6000,
        response_mime_type="application/json",
    )
    print(f"[TIMER] gemini.generate_text: {time.time() - start:.4f}s")
    print("[GEMINI][suggestion][primary] raw output:")
    print(raw_text)
    # When using `response_mime_type="application/json"`, the response is often pure JSON
    # without extra text. Try a direct parse first, then fall back to extraction.
    parsed = None
    try:
        direct = json.loads(raw_text)
        parsed = direct if isinstance(direct, dict) else None
    except Exception:
        parsed = extract_json_obj(raw_text)
    if parsed is None:
        # Retry once with a shorter, stricter prompt (helps when the model stops early).
        retry_prompt = (
            "JSON only. Follow the exact output schema and return complete valid JSON.\n"
            f'ITEM: {json.dumps(slim_attrs, separators=(",", ":"))}\n'
            f"CONTEXT: age_group={age_group}, gender={gender}, season={season}, occasions={','.join(occasions)}.\n"
            f'No item may use category "{anchor_category}".\n'
            f"Need exactly {len(occasions)} outfits (max 2) and each must include: occasion, style_title, items, style_notes, color_palette.\n"
            f"Items must include: category,type,color,description,enrichment,shopping_keywords.\n"
            "Use concise text fields: style_notes <= 180 chars; description <= 120; enrichment <= 110; shopping_keywords <= 90."
        )
        start = time.time()
        raw_text = generate_text(
            retry_prompt,
            model_name=settings.LLM_MODEL,
            temperature=0.0,
            max_output_tokens=4096,
            response_mime_type="application/json",
        )
        print(f"[TIMER] gemini.generate_text (retry): {time.time() - start:.4f}s")
        print("[GEMINI][suggestion][retry] raw output:")
        print(raw_text)
        try:
            direct = json.loads(raw_text)
            parsed = direct if isinstance(direct, dict) else None
        except Exception:
            parsed = extract_json_obj(raw_text)

    if parsed is None:
        # Final fallback: salvage complete outfit objects from truncated model output.
        salvaged_outfits = _salvage_outfit_objects_from_raw(raw_text)
        if salvaged_outfits:
            parsed = {
                "anchor_item": _extract_json_string_field(raw_text, "anchor_item")
                or f'{item_attributes.get("item_type", "item")} {item_attributes.get("color", "")}'.strip(),
                "gender_context": _extract_json_string_field(raw_text, "gender_context") or gender,
                "age_group": _extract_json_string_field(raw_text, "age_group") or age_group,
                "outfits": salvaged_outfits,
            }
            print(f"[GEMINI][suggestion] salvaged outfits: {len(salvaged_outfits)}")
    if parsed is not None:
        # Normalize/validate shape to avoid crashes when the model returns unexpected types.
        outfits_val = parsed.get("outfits")
        if isinstance(outfits_val, dict):
            outfits_list = [outfits_val]
        elif isinstance(outfits_val, list):
            outfits_list = outfits_val
        else:
            outfits_list = []

        # Keep only dict outfits; drop anything else (strings/nulls/etc.)
        outfits_list = [o for o in outfits_list if isinstance(o, dict)]
        parsed["outfits"] = outfits_list

        # Normalize each outfit's items list to list[dict]
        for outfit in outfits_list:
            items_val = outfit.get("items")
            if isinstance(items_val, dict):
                items_list = [items_val]
            elif isinstance(items_val, list):
                items_list = items_val
            else:
                items_list = []
            outfit["items"] = [it for it in items_list if isinstance(it, dict)]

        # Enforce: remove any suggested item whose category OR any text field
        # contains a keyword belonging to an excluded category.
        # Scanning type + description + shopping_keywords catches items where the
        # LLM puts the garment noun in description ("a pair of jeans") but not
        # in type ("straight leg") — the most common slip-through pattern.
        _excl_kws = set()
        for _cat in excluded_categories:
            _excl_kws.update(CATEGORY_INFER_KEYWORDS.get(_cat, ()))
        for outfit in parsed.get("outfits", []):
            items = outfit.get("items") or []
            kept = []
            for it in items:
                cat = (it.get("category") or "").strip().lower()
                if cat in excluded_categories:
                    continue
                if _excl_kws:
                    # Concatenate all text fields that could identify the garment type
                    item_text = " ".join(
                        (it.get(f) or "") for f in ("type", "description", "shopping_keywords")
                    ).lower()
                    if any(kw in item_text for kw in _excl_kws):
                        continue
                kept.append(it)
            outfit["items"] = kept
        # Enforce: drop platform shoes entirely (banned silhouette).
        _PLATFORM_RE = re.compile(r"\bplatform\b", re.IGNORECASE)
        for outfit in parsed.get("outfits", []):
            outfit["items"] = [
                it for it in (outfit.get("items") or [])
                if not (
                    (it.get("category") or "").strip().lower() == "shoes"
                    and _PLATFORM_RE.search(it.get("type", "") + " " + it.get("description", ""))
                )
            ]

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

        # Post-enforce: if shoes are "summer-style" flats (mesh/ballet flats),
        # avoid describing the main top as a warm/heavy knit.
        # This prevents obvious season/vibe mismatches in the UI.
        def _bag_of_text(it: dict) -> str:
            return f"{(it.get('type') or '')} {(it.get('description') or '')} {(it.get('shopping_keywords') or '')}".lower()

        for outfit in parsed.get("outfits", []):
            items = outfit.get("items") or []
            if not isinstance(items, list):
                continue

            shoes_items = [it for it in items if (it.get("category") or "").strip().lower() == "shoes"]
            top_items = [it for it in items if (it.get("category") or "").strip().lower() == "top"]
            if not shoes_items or not top_items:
                continue

            shoes_text = " ".join(_bag_of_text(it) for it in shoes_items)
            shoes_are_summer_flats = any(k in shoes_text for k in ("ballet flat", "ballet", "mesh", "flats"))
            if not shoes_are_summer_flats:
                continue

            # Only rewrite the first top (the "main" top) to keep changes minimal.
            top = top_items[0]
            top_text = _bag_of_text(top)
            top_is_warm_knit = any(k in top_text for k in ("sweater", "hoodie", "turtleneck", "cardigan", "knit"))
            if not top_is_warm_knit:
                continue

            # Rewrite to explicitly lightweight/summer-friendly.
            # Keep the general "knit" concept if present, but change it to "lightweight".
            if isinstance(top.get("type"), str) and "knit" in top["type"].lower():
                top["type"] = re.sub(r"\bknit\b", "lightweight knit", top["type"], flags=re.IGNORECASE)
                top["type"] = top["type"].replace("lightweight lightweight knit", "lightweight knit")
            else:
                top["type"] = "lightweight knit top"

            # Make sure description/enrichment mention breathable/light fabric.
            for key in ("description", "enrichment"):
                val = top.get(key)
                if isinstance(val, str):
                    if "lightweight" not in val.lower():
                        val = f"Lightweight and breathable — {val}"
                    val = re.sub(r"\b(warm|heavy)\b", "light", val, flags=re.IGNORECASE)
                    top[key] = val

            # If shopping keywords exist, remove overly warm terms and add breathable.
            sk = top.get("shopping_keywords")
            if isinstance(sk, str):
                sk2 = sk.replace("wool", "").replace("winter", "").replace("heavy", "").strip()
                if "breathable" not in sk2.lower():
                    sk2 = (sk2 + " breathable").strip()
                top["shopping_keywords"] = sk2

        _clamp_generated_text(parsed)
        _log_outfit_summary(parsed)
        print(f"[GEMINI][suggestion] parsed outfits: {len(parsed.get('outfits') or [])}")
        return parsed

    print("[GEMINI][suggestion] parse failed; returning raw output")
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
