"""Image utility helpers shared across AI generators."""

import io

from PIL import Image

IMAGE_MAX_SIZE = 512
IMAGE_JPEG_QUALITY = 78


def resize_and_compress(image_bytes: bytes, output_path: str) -> str:
    """Resize to IMAGE_MAX_SIZE and save as JPEG; returns the saved path."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    resample = (
        getattr(Image, "Resampling", Image).LANCZOS
        if hasattr(Image, "Resampling")
        else Image.LANCZOS
    )
    img.thumbnail((IMAGE_MAX_SIZE, IMAGE_MAX_SIZE), resample)
    import os
    base, _ = os.path.splitext(output_path)
    out_path = base + ".jpg"
    img.save(out_path, "JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    return out_path
