import json
import re

def load_outfit_db(path: str = "polyvore_converted.json") -> list:
    with open(path) as f:
        return json.load(f)


def score_outfit(outfit: dict, item: dict) -> float:
    """Simple keyword-based similarity score between item and outfit."""
    score = 0.0
    outfit_text = json.dumps(outfit).lower()

    # Match item type
    item_type = item.get("item_type", "").lower()
    for word in item_type.split():
        if word in outfit_text:
            score += 2.0

    # Match color
    primary_color = item.get("color", {}).get("primary", "").lower()
    if primary_color and primary_color in outfit_text:
        score += 1.5

    # Match style
    style = item.get("style_category", "").lower()
    if style and style in outfit_text:
        score += 1.0

    # Match season
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
                # items are plain strings, not dicts
                names = ", ".join(item_list[:2])
                lines.append(f"  {category}: {names}")
        lines.append("")
    return "\n".join(lines)