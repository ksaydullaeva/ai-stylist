"""
Gemini-based outfit image generator.
Generates per-item studio product photos for each outfit.
"""

import os
import time
import uuid

from dotenv import load_dotenv
import google.generativeai as genai
from pathlib import Path

from utils.images import resize_and_compress


class OutfitImageGenerator:
    def __init__(self):
        print("Initializing Gemini Image Generator...")
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash-image")
        print("Gemini API ready")

    def _generate_single_image(
        self,
        prompt: str,
        output_path: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> str:
        """Call Gemini to generate one product image; returns saved path or '' on failure."""
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
