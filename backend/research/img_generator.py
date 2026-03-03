# img_generator.py
# Intermediate Gemini generator that adds flat-lay composition by feeding all
# previously-generated individual-item images back into Gemini alongside the
# user's source image.
#
# Known issue: generate_full_suite() returns a list[str] instead of a dict,
# which is incompatible with what routers/api.py expects.  That mismatch was
# the reason this version was superseded by image_generator_api_advanced.py.

import io
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

IMAGE_MAX_SIZE = 512
IMAGE_JPEG_QUALITY = 78


def _resize_and_compress(image_bytes: bytes, output_path: str) -> str:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    resample = (
        getattr(Image, "Resampling", Image).LANCZOS
        if hasattr(Image, "Resampling")
        else Image.LANCZOS
    )
    img.thumbnail((IMAGE_MAX_SIZE, IMAGE_MAX_SIZE), resample)
    base, _ = os.path.splitext(output_path)
    out_path = base + ".jpg"
    img.save(out_path, "JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    return out_path


class OutfitImageGenerator:
    def __init__(self):
        print("🔄 Initializing Gemini Image Generator (img_generator)...")
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GOOGLE_API_KEY not found in environment variables")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash-image")
        print("✅ Gemini API ready")

    def _generate_single_image(
        self,
        prompt: str,
        output_path: str,
        source_image_path: str | None = None,
        max_retries: int = 2,
        base_delay: float = 1.0,
    ) -> str:
        """Generate one image from a text prompt with optional image context."""
        content_parts = [prompt]

        if source_image_path and os.path.exists(source_image_path):
            img_path = Path(source_image_path)
            mime_type = (
                "image/jpeg"
                if img_path.suffix.lower() in (".jpg", ".jpeg")
                else "image/png"
            )
            content_parts.insert(
                0,
                {"inline_data": {"mime_type": mime_type, "data": img_path.read_bytes()}},
            )

        for attempt in range(max_retries):
            try:
                t0 = time.time()
                response = self.model.generate_content(content_parts)
                print(f"    [API call: {time.time() - t0:.2f}s]")

                if not response.candidates or not response.candidates[0].content.parts:
                    raise ValueError("No candidates returned")

                for part in response.candidates[0].content.parts:
                    image_bytes = None
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_bytes = part.inline_data.data
                    elif hasattr(part, "blob") and part.blob:
                        image_bytes = part.blob.data
                    if image_bytes:
                        saved = _resize_and_compress(image_bytes, output_path)
                        print(f"✅ Saved → {saved}")
                        return saved

                print(f"❌ No image in response for: {prompt[:60]}...")

            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))

        return ""

    def outfit_to_flatlay_prompt(self, outfit_data: dict, outfit_index: int = 0) -> str:
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        item_desc = ", ".join(f"{i['color']} {i['type']}" for i in items)
        return (
            f"A realistic fashion flat lay overhead view: {item_desc}. "
            "Each item displayed separately with clear space between them, no overlapping. "
            "White background. Photorealistic."
        )

    def generate_full_suite(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_dir: str = "outfits",
        source_image_path: str | None = None,
        per_request_delay: float = 1.5,
    ) -> list[str]:
        """Generate individual item images then compose a flat lay.

        NOTE: Returns list[str] (all image paths, flat lay last).
        This differs from the expected dict return type; see image_generator_api_advanced.py
        for the corrected version that returns {"individual_items": [...], "flat_lay": "..."}.
        """
        os.makedirs(output_dir, exist_ok=True)
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        gender = outfit_data.get("gender_context", "adult")
        age_group = outfit_data.get("age_group", "adult")
        saved_item_paths: list[str] = []

        # 1. Individual item images
        for i, item in enumerate(items):
            filename = f"item_{uuid.uuid4().hex[:6]}_{item['type'].replace(' ', '_')}.jpg"
            out_path = os.path.join(output_dir, filename)
            prompt = (
                f"Generate an IMAGE. Studio product photo of a {item['color']} {item['type']} "
                f"on a clean white background. High resolution, for {age_group} {gender}. "
                "Return only the image, no text."
            )
            path = self._generate_single_image(prompt, out_path)
            print(f"⏱️  Item {i + 1}/{len(items)} ({item.get('type', '')})")
            if path:
                saved_item_paths.append(path)
            time.sleep(per_request_delay)

        # 2. Flat lay: feed all item images + source image back to Gemini
        flat_lay_path = os.path.join(output_dir, f"flatlay_{uuid.uuid4().hex[:6]}.jpg")
        flat_lay_result = ""
        try:
            content_parts: list = []

            if source_image_path and os.path.exists(source_image_path):
                src = Path(source_image_path)
                mime = "image/jpeg" if src.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                content_parts.append(
                    {"inline_data": {"mime_type": mime, "data": src.read_bytes()}}
                )

            for img_path_str in saved_item_paths:
                p = Path(img_path_str)
                if not p.exists():
                    continue
                mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                content_parts.append(
                    {"inline_data": {"mime_type": mime, "data": p.read_bytes()}}
                )

            flat_lay_prompt = self.outfit_to_flatlay_prompt(outfit_data, outfit_index)
            content_parts.append(
                flat_lay_prompt
                + f" Arrange all {len(content_parts)} provided product images into a "
                "cohesive flat lay. Display each item separately. White background. "
                "Return only the image, no text."
            )

            t0 = time.time()
            response = self.model.generate_content(content_parts)
            print(f"⏱️  Flat lay call: {time.time() - t0:.2f}s")

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    image_bytes = None
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_bytes = part.inline_data.data
                    elif hasattr(part, "blob") and part.blob:
                        image_bytes = part.blob.data
                    if image_bytes:
                        saved = _resize_and_compress(image_bytes, flat_lay_path)
                        print(f"✅ Flat lay saved → {saved}")
                        flat_lay_result = saved
                        break

        except Exception as e:
            print(f"❌ Flat lay failed: {e}")

        # BUG: should return dict; returns list instead (items + flat lay at end)
        return saved_item_paths + ([flat_lay_result] if flat_lay_result else [])

    def generate_all_outfits(
        self,
        outfit_data: dict,
        output_dir: str = ".",
        source_image_path: str | None = None,
    ) -> list:
        """Run generate_full_suite for every outfit."""
        os.makedirs(output_dir, exist_ok=True)
        results = []
        outfits = outfit_data.get("outfits", [])
        for i in range(len(outfits)):
            print(f"\n--- Outfit {i + 1}/{len(outfits)} ---")
            result = self.generate_full_suite(
                outfit_data,
                outfit_index=i,
                output_dir=output_dir,
                source_image_path=source_image_path,
            )
            results.append(result)
        return results
