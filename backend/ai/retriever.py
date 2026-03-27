"""RAG retriever: keyword-based similarity search over the Polyvore outfit database."""

import json


def load_outfit_db(path: str) -> list:
    with open(path) as f:
        return json.load(f)


def score_outfit(outfit: dict, item: dict) -> float:
    """Keyword-based similarity score between a wardrobe item and a reference outfit."""
    score = 0.0
    outfit_text = json.dumps(outfit).lower()

    item_type = item.get("item_type", "").lower()
    for word in item_type.split():
        if word in outfit_text:
            score += 2.0

    # Color can be returned as:
    # - {"primary": "...", "secondary": "..."} (older/local models)
    # - "navy blue" (Gemini captions)
    # - ["navy blue", "white"] (some prompts)
    color_val = item.get("color")
    color_candidates: list[str] = []
    if isinstance(color_val, dict):
        for k in ("primary", "secondary"):
            v = color_val.get(k)
            if isinstance(v, str) and v.strip():
                color_candidates.append(v.strip())
    elif isinstance(color_val, list):
        for v in color_val:
            if isinstance(v, str) and v.strip():
                color_candidates.append(v.strip())
    elif isinstance(color_val, str) and color_val.strip():
        color_candidates.append(color_val.strip())

    if any(c.lower() in outfit_text for c in color_candidates):
        score += 1.5

    style = item.get("style_category", "").lower()
    if style and style in outfit_text:
        score += 1.0

    season = item.get("season", "").lower()
    if season and season in outfit_text:
        score += 0.5

    return score


def retrieve_similar_outfits(item: dict, db: list, top_k: int = 3) -> list:
    scored = [(score_outfit(o, item), o) for o in db]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [o for _, o in scored[:top_k]]


def format_for_prompt(similar_outfits: list) -> str:
    lines = []
    for i, outfit in enumerate(similar_outfits, 1):
        lines.append(f"Example Outfit {i}:")
        items = outfit.get("items", {})
        for category, item_list in items.items():
            if item_list:
                names = ", ".join(item_list[:2])
                lines.append(f"  {category}: {names}")
        lines.append("")
    return "\n".join(lines)
