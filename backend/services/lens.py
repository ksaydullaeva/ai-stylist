"""
Lens services: query Zara product embeddings stored in Chroma.

Collection found in chroma.sqlite3: `zara_products`, dim=512, cosine space.
Metadata keys include: product_id, name, zara_category, image_path, chroma:document.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
import numpy as np
import open_clip
import torch
from PIL import Image

from core.config import settings


# Existing collection in your DB appears to be TEXT-embedded (source_key="#document").
# For Lens image search we use a separate image-embedded collection built offline.
ZARA_COLLECTION_NAME = "zara_products"  # legacy / reference


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.PersistentClient(path=str(settings.CHROMA_ZARA_DIR))
    # IMPORTANT: Do not pass an embedding_function here.
    # The collection already has a persisted embedding function config; providing a new one
    # causes an "embedding function conflict" error. We embed the query image ourselves and
    # use query_embeddings.
    return client.get_collection(name=settings.ZARA_IMAGE_COLLECTION)


@lru_cache(maxsize=1)
def _get_openclip():
    """
    Returns (model, preprocess, device).
    Assumes the Chroma collection was built with a 512-d OpenCLIP image embedding
    (common: ViT-B-32). If your dataset used a different CLIP variant, update these names
    to match, otherwise retrieval quality will be poor even if dimensions match.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
    model.to(device)
    model.eval()
    return model, preprocess, device


def _embed_image_512(img: Image.Image) -> list[float]:
    model, preprocess, device = _get_openclip()
    x = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        feat = model.encode_image(x)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    v = feat.squeeze(0).detach().cpu().float().numpy()
    return v.astype(np.float32).tolist()


def query_similar_products(
    image_path: str | Path,
    n_results: int = 12,
    where: dict[str, Any] | None = None,
) -> dict:
    """
    Query the Zara embedding collection using an uploaded image.
    Returns the raw Chroma query response (ids, distances, metadatas, documents).
    """
    p = Path(image_path)
    with Image.open(p) as img:
        img = img.convert("RGB")
        emb = _embed_image_512(img)
        res = _get_collection().query(
            query_embeddings=[emb],
            n_results=n_results,
            where=where,
            include=["metadatas", "distances", "documents"],
        )
    return res


def safe_rel_image_path(abs_path: str) -> str | None:
    """
    Convert an absolute dataset image path (from Chroma metadata) into a safe relative path
    under ZARA_DATASET_ROOT. Returns None if it does not fall under the root.
    """
    if not abs_path:
        return None
    root = Path(settings.ZARA_DATASET_ROOT).expanduser().resolve()
    try:
        p = Path(abs_path).expanduser().resolve()
        rel = p.relative_to(root)
        return rel.as_posix()
    except Exception:
        return None

