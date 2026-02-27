# polyvore_converter.py
import pandas as pd
import glob
import json

CATEGORY_MAP = {
    # Tops
    "Tops": "top", "Blouses": "top", "Shirts": "top", "Tank Tops": "top",
    "Tunics": "top", "Sweaters": "top", "Hoodies": "top", "Cardigans": "top",
    "Sweatshirts": "top", "Crop Tops": "top", "Turtlenecks": "top",
    "Day Dresses": "top", "Night Out Dresses": "top", "Casual Dresses": "top",
    "Cocktail Dresses": "top", "Maxi Dresses": "top", "Mini Dresses": "top",
    "Jumpsuits": "top", "Rompers": "top",

    # Bottoms
    "Jeans": "bottom", "Pants": "bottom", "Trousers": "bottom",
    "Shorts": "bottom", "Leggings": "bottom", "Knee Length Skirts": "bottom",
    "Mini Skirts": "bottom", "Maxi Skirts": "bottom", "Skirts": "bottom",
    "Joggers": "bottom",

    # Shoes
    "Sandals": "shoes", "Pumps": "shoes", "Ankle Booties": "shoes",
    "Sneakers": "shoes", "Boots": "shoes", "Flats": "shoes",
    "Loafers": "shoes", "Heels": "shoes", "Wedges": "shoes",
    "Mules": "shoes", "Oxfords": "shoes", "Platforms": "shoes",
    "Over the Knee Boots": "shoes", "Slip Ons": "shoes",

    # Accessories
    "Earrings": "accessory", "Necklaces": "accessory", "Bracelets & Bangles": "accessory",
    "Rings": "accessory", "Sunglasses": "accessory", "Watches": "accessory",
    "Belts": "accessory", "Scarves": "accessory", "Hats": "accessory",
    "Hair Accessories": "accessory", "Brooches": "accessory",

    # Bags
    "Shoulder Bags": "accessory", "Clutches": "accessory", "Handbags": "accessory",
    "Tote Bags": "accessory", "Crossbody Bags": "accessory", "Backpacks": "accessory",
    "Satchels": "accessory", "Wristlets": "accessory",

    # Outerwear
    "Jackets": "outerwear", "Coats": "outerwear", "Blazers": "outerwear",
    "Leather Jackets": "outerwear", "Denim Jackets": "outerwear",
    "Trench Coats": "outerwear", "Parkas": "outerwear", "Vests": "outerwear",
    "Bomber Jackets": "outerwear",
}

REQUIRED_CATEGORIES = {"top", "bottom", "shoes"}


def convert_polyvore(output_path: str = "polyvore_converted.json", max_outfits: int = 1000):
    # Load all parquet files
    print("📦 Loading parquet files...")
    dfs = [pd.read_parquet(f) for f in sorted(glob.glob("polyvore-dataset/data/*.parquet"))]
    df = pd.concat(dfs, ignore_index=True)
    print(f"✅ Loaded {len(df)} items across {df['item_ID'].str.rsplit('_', n=1).str[0].nunique()} outfits")

    # Group by outfit ID
    df["outfit_id"] = df["item_ID"].str.rsplit("_", n=1).str[0]
    df["mapped_category"] = df["category"].map(CATEGORY_MAP)

    # Drop unmapped categories
    df = df.dropna(subset=["mapped_category"])

    converted = []

    for outfit_id, group in df.groupby("outfit_id"):
        # Group items by mapped category
        outfit_items = {"top": [], "bottom": [], "shoes": [], "accessory": [], "outerwear": []}

        for _, row in group.iterrows():
            cat = row["mapped_category"]
            outfit_items[cat].append(row["text"].strip())

        # Skip outfits missing required categories
        has_required = all(len(outfit_items[c]) > 0 for c in REQUIRED_CATEGORIES)
        if not has_required:
            continue

        converted.append({
            "outfit_id": outfit_id,
            "items": {
                "top":       outfit_items["top"],
                "bottom":    outfit_items["bottom"],
                "shoes":     outfit_items["shoes"],
                "accessory": outfit_items["accessory"],
                "outerwear": outfit_items["outerwear"],
            }
        })

        if len(converted) >= max_outfits:
            break

    with open(output_path, "w") as f:
        json.dump(converted, f, indent=2)

    print(f"✅ Saved {len(converted)} outfits → {output_path}")
    print(f"\nSample outfit:")
    print(json.dumps(converted[0], indent=2))


if __name__ == "__main__":
    convert_polyvore(max_outfits=1000)