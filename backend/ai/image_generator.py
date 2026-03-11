"""
Gemini-based outfit image generator.
Generates per-item studio product photos for each outfit.
Supports virtual try-on: person photo + outfit items → person wearing the outfit.
"""

import io
import os
import re
import time
import uuid

import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
from PIL import Image

from core.config import settings
from utils.images import resize_and_compress

# Max input images for try-on; Gemini supports up to 3 total
TRY_ON_MAX_ITEM_IMAGES = 2  # when no source garment
TRY_ON_MAX_ITEM_IMAGES_WITH_GARMENT = 1  # person + garment + 1 outfit item

# Backend dir: same as core.config, so .env is found whether running locally or in Docker
_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _get_google_api_key() -> str:
    # 1. From pydantic settings (env + env_file)
    key = (settings.GOOGLE_API_KEY or "").strip()
    if key:
        return key
    # 2. Load backend/.env via dotenv
    env_path = _BACKEND_DIR / ".env"
    load_dotenv(env_path)
    key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if key:
        return key
    # 3. Read .env file directly (avoids dotenv/pydantic quirks in Docker)
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_API_KEY=") and not line.startswith("GOOGLE_API_KEY=#"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key
    return ""


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate limit" in str(exc)


def _retry_delay_for_quota(exc: Exception) -> float:
    """Parse 'Please retry in X.XXs' from error message, or return 10.0."""
    msg = str(exc)
    m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
    if m:
        return max(10.0, float(m.group(1)) + 1)
    return 10.0


class OutfitImageGenerator:
    def __init__(self):
        print("Initializing Gemini Image Generator...")
        api_key = _get_google_api_key()
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not set. Add it to backend/.env or set the environment variable."
            )
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash-image")
        print("Gemini API ready")

    def _generate_single_image(
        self,
        prompt: str,
        output_path: str,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ) -> str:
        """Call Gemini to generate one product image; returns saved path or '' on failure.
        Uses 5 retries so quota/429 can recover (with 10s delay for rate limit)."""
        attempt = 0
        while attempt < max_retries:
            try:
                t0 = time.time()
                response = self.model.generate_content([prompt])
                print(f"    [API call: {time.time() - t0:.2f}s]")

                if not response.candidates or not response.candidates[0].content.parts:
                    raise ValueError("No image data returned")

                finish_reason = getattr(response.candidates[0], "finish_reason", None)
                if finish_reason:
                    print(f"finish_reason: {finish_reason}")

                for part in response.candidates[0].content.parts:
                    image_bytes = (
                        getattr(part.inline_data, "data", None)
                        if hasattr(part, "inline_data") and part.inline_data
                        else getattr(part.blob, "data", None)
                        if hasattr(part, "blob") and part.blob
                        else None
                    )
                    if image_bytes:
                        saved = resize_and_compress(image_bytes, output_path)
                        print(f"Saved -> {saved}")
                        return saved

                try:
                    resp_text = getattr(response, "text", "") or ""
                    if resp_text:
                        print(f"Model text (excerpt): {resp_text[:200]}")
                except Exception:
                    pass
                raise ValueError("Response contained no image parts")

            except Exception as e:
                print(f"Generation failed (attempt {attempt + 1}): {e}")
                attempt += 1
                if attempt < max_retries:
                    if _is_quota_error(e):
                        delay = _retry_delay_for_quota(e)
                        print(f"Quota/rate limit hit. Retrying in {delay:.1f}s…")
                    else:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(f"Retrying in {delay:.1f}s")
                    time.sleep(delay)

        return ""

    def generate_full_suite(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_dir: str = "outfits",
        source_image_path: str | None = None,
        per_request_delay: float = 1.5,
    ) -> dict:
        """Generate individual item images for one outfit.

        Args:
            source_image_path: Accepted for API compatibility; not used (text-only prompts).

        Returns:
            {"individual_items": [path, ...]}
        """
        os.makedirs(output_dir, exist_ok=True)
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        gender = outfit_data.get("gender_context", "adult")
        age_group = outfit_data.get("age_group", "adult")
        individual_items: list[str] = []

        for i, item in enumerate(items):
            filename = f"item_{uuid.uuid4().hex[:6]}_{item['type'].replace(' ', '_')}.jpg"
            item_path = os.path.join(output_dir, filename)
            prompt = (
                f"Generate an IMAGE. Professional studio product photo of a {item['color']} {item['type']} "
                f"on a clean white background. Minimalist, evenly lit, high resolution. "
                f"For {age_group} {gender}. Realistic. Return only the image, no text."
            )
            t0 = time.time()
            path = self._generate_single_image(prompt, item_path)
            print(f"Item {i + 1}/{len(items)} ({item.get('type', '')}): {time.time() - t0:.2f}s")
            if path:
                individual_items.append(path)
            time.sleep(per_request_delay)

        return {"individual_items": individual_items}

    def _image_to_jpeg_bytes(self, image_path: str) -> bytes:
        """Load image from path (any PIL-supported format), convert to RGB, return JPEG bytes.
        Ensures Gemini always receives valid image/jpeg and avoids 'unknown format' errors
        for WebP, HEIC, etc. that were previously mislabeled as PNG."""
        p = Path(image_path)
        if not p.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        try:
            img = Image.open(p)
        except Exception as e:
            raise ValueError(
                f"Unsupported or corrupt image format ({p.suffix or 'unknown'}). "
                "Please use JPEG or PNG."
            ) from e
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90, optimize=True)
        return buf.getvalue()

    def _image_part(self, image_path: str) -> dict:
        """Build an inline_data part for Gemini from a file path. Normalizes to JPEG so
        Gemini never receives mislabeled or unsupported formats (e.g. WebP sent as PNG)."""
        data = self._image_to_jpeg_bytes(image_path)
        return {"inline_data": {"mime_type": "image/jpeg", "data": data}}

    def try_on(
        self,
        person_image_path: str,
        outfit_item_paths: list[str],
        outfit_description: str,
        output_path: str,
        source_garment_path: str | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> str:
        """Generate a single image of the person wearing the outfit using Gemini.

        Args:
            person_image_path: Path to photo of the person (full body or upper body).
            outfit_item_paths: Paths to generated outfit item images.
            outfit_description: Short text description of the outfit (e.g. colors and types).
            output_path: Where to save the generated try-on image.
            source_garment_path: Optional path to the source garment image — the initial clothing item
                image the user sent (with their optional self image) at the start of the flow.

        Returns:
            Path to the saved try-on image, or "" on failure.
        """
        content_parts: list = []
        # 1. Person image first
        content_parts.append(self._image_part(person_image_path))
        # 2. Optional: source garment = initial item image the user sent (with their optional self image)
        if source_garment_path and Path(source_garment_path).exists():
            content_parts.append(self._image_part(source_garment_path))
        # 3. Outfit item images (1 when garment provided, else up to 2; max 3 images total)
        max_items = TRY_ON_MAX_ITEM_IMAGES_WITH_GARMENT if source_garment_path else TRY_ON_MAX_ITEM_IMAGES
        for path in outfit_item_paths[:max_items]:
            if path and Path(path).exists():
                content_parts.append(self._image_part(path))
        # 4. Prompt for virtual try-on
        if source_garment_path and Path(source_garment_path).exists():
            prompt = (
                "Generate a single photorealistic IMAGE of this person wearing this outfit. "
                "First image is the person (full body). Second image is the anchor garment the user owns. "
                "The following image(s) are other suggested outfit items. "
                "CRITICAL: Keep every clothing item exactly as in the reference images — same colors, same texture, "
                "same design and style. Do not alter the anchor item or the suggested items. "
                "Remove the background from the person: show the person on a clean, plain neutral background "
                "(e.g. white, light gray, or simple studio backdrop). Do not keep the person's original background "
                "and do not add a new scenic or decorative background. "
                f"Outfit: {outfit_description}. "
                "Same pose and body type, realistic fit and lighting. Preserve the person's face and skin. "
                "Return only the image, no text."
            )
        else:
            prompt = (
                "Generate a single photorealistic IMAGE of this person wearing this outfit. "
                "First image is the person (full body). The following images are clothing items from the outfit. "
                "CRITICAL: Keep every clothing item exactly as in the reference images — same colors, same texture, "
                "same design and style. Do not alter any item. "
                "Remove the background from the person: show the person on a clean, plain neutral background "
                "(e.g. white, light gray, or simple studio backdrop). Do not keep the person's original background "
                "and do not add a new scenic or decorative background. "
                f"Outfit: {outfit_description}. "
                "Same pose and body type, realistic fit and lighting. Preserve the person's face and skin. "
                "Return only the image, no text."
            )
        content_parts.append(prompt)

        attempt = 0
        while attempt < max_retries:
            try:
                t0 = time.time()
                response = self.model.generate_content(content_parts)
                print(f"    [Try-on API call: {time.time() - t0:.2f}s]")

                if not response.candidates or not response.candidates[0].content.parts:
                    raise ValueError("No image data returned")

                for part in response.candidates[0].content.parts:
                    image_bytes = (
                        getattr(part.inline_data, "data", None)
                        if hasattr(part, "inline_data") and part.inline_data
                        else getattr(part.blob, "data", None)
                        if hasattr(part, "blob") and part.blob
                        else None
                    )
                    if image_bytes:
                        saved = resize_and_compress(image_bytes, output_path)
                        print(f"Try-on saved -> {saved}")
                        return saved

                raise ValueError("Response contained no image parts")

            except Exception as e:
                print(f"Try-on failed (attempt {attempt + 1}): {e}")
                attempt += 1
                if attempt < max_retries:
                    if _is_quota_error(e):
                        delay = _retry_delay_for_quota(e)
                        print(f"Quota/rate limit hit. Retrying in {delay:.1f}s…")
                    else:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(f"Retrying in {delay:.1f}s")
                    time.sleep(delay)

        return ""

    def generate_all_outfits(
        self,
        outfit_data: dict,
        output_dir: str = ".",
        source_image_path: str | None = None,
        per_request_delay: float = 1.5,
    ) -> list[dict]:
        """Generate item images for every outfit in outfit_data.

        Returns:
            [{"individual_items": [...]}, ...]
        """
        os.makedirs(output_dir, exist_ok=True)
        outfits = outfit_data.get("outfits", [])
        t_total = time.time()
        results = []
        for i in range(len(outfits)):
            print(f"\n--- Outfit {i + 1}/{len(outfits)} ---")
            t_suite = time.time()
            result = self.generate_full_suite(
                outfit_data,
                outfit_index=i,
                output_dir=output_dir,
                source_image_path=source_image_path,
                per_request_delay=per_request_delay,
            )
            print(f"Outfit {i + 1} total: {time.time() - t_suite:.2f}s")
            results.append({"individual_items": result.get("individual_items") or []})
        print(f"\ngenerate_all_outfits TOTAL: {time.time() - t_total:.2f}s for {len(outfits)} outfit(s)")
        return results
