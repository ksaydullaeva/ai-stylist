"""
Build an IMAGE-embedded Chroma collection for Zara Lens.

Why:
- The existing `zara_products` collection in chroma.sqlite3 was built with embeddings sourced
  from `#document` (text). Lens needs image→image similarity.

What it does:
- Reads ids + metadatas (+ document) from the existing `zara_products` collection
- Computes OpenCLIP image embeddings (512-d) for each metadata["image_path"]
- Writes to a NEW collection (default: settings.ZARA_IMAGE_COLLECTION, e.g. `zara_products_image`)

Run:
  python -m scripts.build_zara_image_collection

Optional env vars (backend/.env or shell):
  CHROMA_ZARA_DIR=...            # default backend/chroma_zara
  ZARA_IMAGE_COLLECTION=...      # default zara_products_image
"""

from __future__ import annotations

import math
from pathlib import Path

import chromadb
import numpy as np
import open_clip
import torch
from PIL import Image

from core.config import settings


SOURCE_COLLECTION = "zara_products"


def _get_openclip():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    model.to(device)
    model.eval()
    return model, preprocess, device


def _embed_image(model, preprocess, device, image_path: str) -> list[float] | None:
    p = Path(image_path)
    if not p.exists() or not p.is_file():
        return None
    try:
        with Image.open(p) as img:
            img = img.convert("RGB")
            x = preprocess(img).unsqueeze(0).to(device)
            with torch.no_grad():
                feat = model.encode_image(x)
                feat = feat / feat.norm(dim=-1, keepdim=True)
            v = feat.squeeze(0).detach().cpu().float().numpy()
            return v.astype(np.float32).tolist()
    except Exception:
        return None


def main(batch_size: int = 32) -> None:
    client = chromadb.PersistentClient(path=str(settings.CHROMA_ZARA_DIR))
    src = client.get_collection(SOURCE_COLLECTION)

    total = src.count()
    print(f"[lens] Source collection `{SOURCE_COLLECTION}` count: {total}")
    if total == 0:
        raise SystemExit("No items in source collection.")

    # Create/replace destination collection.
    dest_name = settings.ZARA_IMAGE_COLLECTION
    try:
        client.delete_collection(dest_name)
        print(f"[lens] Deleted existing `{dest_name}`")
    except Exception:
        pass
    dest = client.create_collection(name=dest_name, metadata={"source": "open_clip_image", "model": "ViT-B-32"})
    print(f"[lens] Created destination `{dest_name}`")

    model, preprocess, device = _get_openclip()
    print(f"[lens] OpenCLIP device: {device}")

    # Fetch everything from src (small dataset in your current db; safe).
    data = src.get(include=["metadatas", "documents"])
    ids = data.get("ids") or []
    metas = data.get("metadatas") or []
    docs = data.get("documents") or []

    n = len(ids)
    print(f"[lens] Fetched {n} ids from source.")

    added = 0
    skipped = 0

    for start in range(0, n, batch_size):
        end = min(n, start + batch_size)
        batch_ids = ids[start:end]
        batch_metas = metas[start:end]
        batch_docs = docs[start:end] if docs else [None] * (end - start)

        batch_embs = []
        out_ids = []
        out_metas = []
        out_docs = []

        for i, _id in enumerate(batch_ids):
            md = batch_metas[i] or {}
            img_path = md.get("image_path") or ""
            emb = _embed_image(model, preprocess, device, img_path)
            if emb is None:
                skipped += 1
                continue
            out_ids.append(_id)
            out_metas.append(md)
            out_docs.append(batch_docs[i])
            batch_embs.append(emb)

        if out_ids:
            dest.add(
                ids=out_ids,
                embeddings=batch_embs,
                metadatas=out_metas,
                documents=out_docs,
            )
            added += len(out_ids)

        if (start // batch_size) % 5 == 0:
            pct = (end / n) * 100
            print(f"[lens] Progress: {end}/{n} ({pct:.1f}%) | added={added} skipped={skipped}")

    print(f"[lens] Done. added={added} skipped={skipped} into `{dest_name}`")


if __name__ == "__main__":
    main()

