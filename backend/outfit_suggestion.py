import ollama
import json
import re
import time
from outfit_retriever import load_outfit_db, retrieve_similar_outfits, format_for_prompt
from image_generator_api_advanced import OutfitImageGenerator

# Load once at startup
OUTFIT_DB = load_outfit_db("polyvore_converted.json")

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

def generate_outfit_suggestions(item_attributes: dict, occasions: list[str] = None) -> dict:
    total_start = time.time()

    start = time.time()

    if occasions is None:
        occasions = ["casual", "smart-casual", "formal"]

    gender = item_attributes.get("gender", "unisex")
    age_group = item_attributes.get("age_group", "adult")
    season = item_attributes.get("season", "all-season")

    # RAG: retrieve similar outfits
    similar = retrieve_similar_outfits(item_attributes, OUTFIT_DB, top_k=3)
    rag_context = format_for_prompt(similar)

    prompt = f"""Here is a clothing item from the user's wardrobe:

    {json.dumps(item_attributes, indent=2)}

    The user is a {age_group} {gender} person. Generate outfit suggestions accordingly.
    All suggested items must be appropriate for {gender} {age_group} style.

    Occasions to cover: {', '.join(occasions)}.

    SEASON RULES (STRICT — ALL ITEMS MUST MATCH THE SAME SEASON):
    - The user's item is for: {season}. Every suggested item (top, bottom, shoes, accessory, outerwear) MUST be appropriate for that same season.
    - Do NOT mix summer-only items (e.g. slide sandals, flip-flops, open-toe sandals) with fall/winter items (e.g. heavy jackets, scarves, boots).
    - Do NOT mix winter-only items (e.g. heavy coats, warm scarves, boots) with summer items (e.g. sandals, tank tops).
    - Shoes and accessories must match the season: e.g. for fall/winter use boots, loafers, closed-toe shoes; for summer use sandals, espadrilles; for all-season use versatile options.

    STRUCTURE RULES (STRICT — DO NOT VIOLATE):
    - Every outfit MUST include, in its "items" list:
        * Exactly 1 top  (category="top", e.g. shirt, blouse, sweater — not outerwear)
        * Exactly 1 bottom (category="bottom", e.g. pants, skirt, shorts)
        * Exactly 1 pair of shoes (category="shoes")
        * Exactly 1 or 2 accessories (category="accessory", e.g. bag, belt, jewelry, scarf, hat)
        * Optional outerwear (category="outerwear") ONLY if season is {season} and weather requires it
    - Each entry in "items" MUST be a separate object, never merged.
    - The "items" array MUST therefore contain at least 4 and at most 6 objects.
    - For each item, include "enrichment": a short, catchy sentence explaining why this piece enriches the look (e.g. "A crisp white blouse adds a pop of elegance to the outfit.").

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
            "enrichment": "<one catchy sentence why this item enriches the look, e.g. 'A crisp white blouse adds a pop of elegance to the outfit.'>",
            "shopping_keywords": "<gender-specific search keywords e.g. 'women slim fit trousers black'>"
            }}
        ],
        "style_notes": "<why this outfit works>",
        "color_palette": ["<color1>", "<color2>", "<color3>"]
        }}
    ]
    }}"""

    print(f"[TIMER] Preprocessing: {time.time() - start:.4f}s")

    start = time.time()
    response = ollama.chat(
        model="qwen2.5:3b", #llama3.1:8b - 80s
        messages=[
            {"role": "system", "content": FASHION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        options={
            "temperature": 0.7,  # some creativity but still coherent
            "num_predict": 1200,   # cap output tokens — outfits don't need more
            "num_ctx": 2048,
        }
    )

    raw_text = response["message"]["content"]
    print(f"[TIMER] ollama.chat took : {time.time() - start:.4f}s")

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        format_outfit_for_display(json.loads(match.group()))
        return json.loads(match.group())
    
   

    return {"raw": raw_text}


def format_outfit_for_display(outfit_data: dict) -> None:
    """Pretty print outfits for debugging / CLI preview."""
    print(f"\n👕 Anchor Item: {outfit_data.get('anchor_item')}\n")
    
    for outfit in outfit_data.get("outfits", []):
        print(f"{'='*50}")
        print(f"🎯 Occasion : {outfit['occasion'].upper()}")
        print(f"✨ Style    : {outfit['style_title']}")
        print(f"🎨 Palette  : {', '.join(outfit['color_palette'])}")
        print(f"📝 Notes    : {outfit['style_notes']}")
        print(f"\nItems to complete the look:")
        for item in outfit["items"]:
            print(f"{item['type']} — {item['color']} ({item['description']})")
            print(f"Search keywords: '{item['shopping_keywords']}'")
        print()


if __name__ == "__main__":
    from item_captioning import analyze_wardrobe_item 
    image = "examples/navy-blue-jacket.png"
    item = analyze_wardrobe_item(image)
    occasions = item['style_category']
    result = generate_outfit_suggestions(
        item_attributes=item,
        occasions=occasions
    )

    format_outfit_for_display(result)

    # Step 3 — generate flat lay images
    generator = OutfitImageGenerator()
    all_results = []
    outfits = result.get("outfits", [])
    for idx in range(len(outfits)):
        res = generator.generate_full_suite(
            result,
            outfit_index=idx,
            output_dir="outfit_previews",
            source_image_path=image,
        )
        all_results.append(res)

    # Print paths for each outfit: individual item images + flat lay
    print(f"\n🖼️  Generated {len(all_results)} outfit(s)")
    for idx, res in enumerate(all_results):
        occasion = outfits[idx].get("occasion", f"Outfit {idx + 1}") if idx < len(outfits) else f"Outfit {idx + 1}"
        print(f"\n--- {occasion} ---")
        print("  Individual items:")
        for path in res.get("individual_items", []):
            print(f"    {path}")
        print(f"  Flat lay: {res.get('flat_lay', '')}")
