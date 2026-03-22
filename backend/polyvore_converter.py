# polyvore_converter.py
import json
import os
from pathlib import Path

import pandas as pd

_SCRIPT_DIR = Path(__file__).resolve().parent
_POLYVORE_DATASET_DIR = _SCRIPT_DIR / "polyvore-dataset"
_DEFAULT_DATA_DIR = _POLYVORE_DATASET_DIR / "data"


def _load_category_id_map(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            try:
                out[int(parts[0])] = parts[1]
            except ValueError:
                continue
    return out


def _dataframe_from_polyvore_json(dataset_dir: Path) -> pd.DataFrame:
    """Build item rows from official Polyvore *_no_dup.json + category_id.txt (set_id + categoryid)."""
    cat_path = dataset_dir / "category_id.txt"
    if not cat_path.is_file():
        raise FileNotFoundError(f"Missing {cat_path}")
    cat_map = _load_category_id_map(cat_path)
    rows: list[dict] = []
    for split_name in ("train_no_dup.json", "valid_no_dup.json", "test_no_dup.json"):
        split_path = dataset_dir / split_name
        if not split_path.is_file():
            continue
        with split_path.open(encoding="utf-8") as f:
            outfits = json.load(f)
        for outfit in outfits:
            sid = str(outfit["set_id"])
            for item in outfit["items"]:
                cid = item.get("categoryid")
                if cid is None:
                    continue
                cat_name = cat_map.get(cid)
                if cat_name is None:
                    continue
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                idx = item.get("index", 0)
                rows.append(
                    {
                        "item_ID": f"{sid}_{idx}",
                        "category": cat_name,
                        "text": name,
                    }
                )
    if not rows:
        raise ValueError(f"No outfit items parsed from JSON under {dataset_dir}")
    return pd.DataFrame(rows)


def _hf_hub_root() -> Path:
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def _hf_cached_polyvore_parquets() -> list[Path]:
    """Parquet shards from `datasets load_dataset(...)` under the Hugging Face hub cache."""
    hub = _hf_hub_root()
    if not hub.is_dir():
        return []
    return sorted(hub.glob("datasets--*polyvore*/snapshots/*/data/*.parquet"))


def _load_polyvore_dataframe(data_dir: Path | None) -> pd.DataFrame:
    """Prefer parquet in data_dir or polyvore-dataset/data/; else Polyvore JSON splits; else HF hub cache."""
    if data_dir is not None:
        files = sorted(data_dir.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No .parquet files under {data_dir}")
        return _prepare_converter_dataframe(pd.concat([pd.read_parquet(f) for f in files], ignore_index=True))

    pq = sorted(_DEFAULT_DATA_DIR.glob("*.parquet"))
    if pq:
        return _prepare_converter_dataframe(pd.concat([pd.read_parquet(f) for f in pq], ignore_index=True))

    if (_POLYVORE_DATASET_DIR / "train_no_dup.json").is_file():
        print(f"   (using Polyvore JSON splits + category_id.txt in {_POLYVORE_DATASET_DIR})")
        return _prepare_converter_dataframe(_dataframe_from_polyvore_json(_POLYVORE_DATASET_DIR))

    hf = _hf_cached_polyvore_parquets()
    if hf:
        print(f"   (using Hugging Face hub cache: {hf[0].parent})")
        return _prepare_converter_dataframe(pd.concat([pd.read_parquet(f) for f in hf], ignore_index=True))

    raise FileNotFoundError(
        f"No data found: add .parquet under {_DEFAULT_DATA_DIR}, "
        f"or clone Polyvore splits (train_no_dup.json, category_id.txt) into {_POLYVORE_DATASET_DIR}, "
        f"or set data_dir= to a folder with outfit parquet."
    )


def _prepare_converter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects the outfit-oriented text dump: item_ID like '<outfitId>_<itemId>', category, text.
    Hugging Face `owj0421/polyvore` hub files are item-only (item_id, title, …) and cannot be used here.
    """
    lower = {c.lower(): c for c in df.columns}
    if "item_id" in lower and "item_ID" not in df.columns:
        raise ValueError(
            "Found Hugging Face–style Polyvore items (column item_id, no outfit id in the id). "
            "This converter needs the outfit text dump with column item_ID "
            "('<outfitId>_<itemId>'), category, and text. "
            f"Place those parquet files in {_DEFAULT_DATA_DIR}; the HF item catalog cannot be converted to outfits."
        )
    if "item_ID" not in df.columns:
        raise ValueError(
            f"Missing column item_ID. Columns present: {list(df.columns)}"
        )
    for need in ("category", "text"):
        if need not in df.columns:
            raise ValueError(f"Missing column {need}. Columns present: {list(df.columns)}")
    return df

CATEGORY_MAP = {
    # Tops
    "Tops": "top", "Blouses": "top", "Shirts": "top", "Tank Tops": "top",
    "Tunics": "top", "Sweaters": "top", "Hoodies": "top", "Cardigans": "top",
    "Sweatshirts": "top", "T-Shirts": "top", "Crop Tops": "top", "Turtlenecks": "top",
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


def convert_polyvore(
    output_path: str | Path | None = None,
    max_outfits: int = 1000,
    data_dir: Path | None = None,
):
    out = Path(output_path) if output_path is not None else _SCRIPT_DIR / "polyvore_converted.json"

    print("📦 Loading Polyvore data...")
    df = _load_polyvore_dataframe(data_dir)
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

    with open(out, "w") as f:
        json.dump(converted, f, indent=2)

    print(f"✅ Saved {len(converted)} outfits → {out}")
    if converted:
        print(f"\nSample outfit:")
        print(json.dumps(converted[0], indent=2))


if __name__ == "__main__":
    convert_polyvore(max_outfits=10000)