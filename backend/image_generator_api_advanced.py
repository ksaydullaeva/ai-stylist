# image_generator_api.py

import io
import os
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Lower-quality output for faster load: max dimension and JPEG quality
IMAGE_MAX_SIZE = 512
IMAGE_JPEG_QUALITY = 78


def _resize_and_compress(image_bytes: bytes, output_path: str) -> str:
    """Resize and save as JPEG to reduce file size and load time."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    img.thumbnail((IMAGE_MAX_SIZE, IMAGE_MAX_SIZE), resample)
    base, _ = os.path.splitext(output_path)
    out_path = base + ".jpg"
    img.save(out_path, "JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    return out_path

class OutfitImageGenerator:
    def __init__(self):
        print("🔄 Initializing Gemini Image Generator...")
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GOOGLE_API_KEY not found in environment variables")

        genai.configure(api_key=self.api_key)
        # Using the latest generation model
        self.model = genai.GenerativeModel("gemini-2.5-flash-image")
        print("✅ Gemini API ready")

    def _generate_single_image(
        self,
        prompt: str,
        output_path: str,
        source_image_path: str | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> str:
        """Internal helper with optional image context, exponential backoff, and safety diagnostics."""
        attempt = 0
        while attempt < max_retries:
            try:
                content_parts = [prompt]

                # If a source image is provided, prepend it to the prompt parts
                if source_image_path and os.path.exists(source_image_path):
                    img_path = Path(source_image_path)
                    image_data = img_path.read_bytes()
                    mime_type = (
                        "image/jpeg"
                        if img_path.suffix.lower() in [".jpg", ".jpeg"]
                        else "image/png"
                    )
                    content_parts.insert(
                        0,
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_data,
                            }
                        },
                    )

                t_call = time.time()
                response = self.model.generate_content(content_parts)
                print(f"    [API call: {time.time() - t_call:.2f}s]")

                if not response.candidates or not response.candidates[0].content.parts:
                    print(f"❌ No image data returned for: {prompt[:60]}...")
                    # Backoff and retry
                    attempt += 1
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(f"⏳ Retrying in {delay:.1f}s (attempt {attempt}/{max_retries})")
                        time.sleep(delay)
                        continue
                    return ""

                candidate = response.candidates[0]
                finish_reason = getattr(candidate, "finish_reason", None)
                if finish_reason:
                    print(f"ℹ️ finish_reason: {finish_reason}")

                image_bytes = None
                for part in candidate.content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_bytes = part.inline_data.data
                        break
                    if hasattr(part, "blob") and part.blob:
                        image_bytes = part.blob.data
                        break

                if image_bytes:
                    saved_path = _resize_and_compress(image_bytes, output_path)
                    print(f"✅ Saved → {saved_path}")
                    return saved_path

                # If we reach here, model likely replied with text or non-image content.
                # Print a short excerpt so we can see *why* it didn't return an image.
                try:
                    resp_text = getattr(response, "text", "") or ""
                    if resp_text:
                        print(f"📝 Model text (excerpt): {resp_text[:200]}")
                except Exception:
                    pass
                print(f"❌ Non-image response for: {prompt[:60]}...")
                attempt += 1
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    print(f"⏳ Retrying in {delay:.1f}s (attempt {attempt}/{max_retries})")
                    time.sleep(delay)
                    continue
                return ""

            except Exception as e:
                print(f"❌ Generation failed (attempt {attempt + 1}): {e}")
                attempt += 1
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    print(f"⏳ Retrying in {delay:.1f}s after error")
                    time.sleep(delay)
                    continue
                return ""

    def generate_full_suite(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_dir: str = "outfits",
        source_image_path: str | None = None,
        per_request_delay: float = 1.5,
    ):
        """
        Generates individual items and a flat lay.

        Throttling / backoff:
        - Sleeps `per_request_delay` seconds between item requests to avoid rate limits.
        - `_generate_single_image` itself has retry + exponential backoff.
        - To reduce payload size, the source image is used only for the FLAT LAY by default,
          and individual items are generated from text prompts alone.
        """
        os.makedirs(output_dir, exist_ok=True)
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        results = {"individual_items": [], "flat_lay": ""}
        gender = outfit_data.get("gender_context", "adult")
        age_group = outfit_data.get("age_group", "adult")

        # 1. Generate Individual Items (text-only by default to keep payload light)
        for i, item in enumerate(items):
            item_filename = f"item_{uuid.uuid4().hex[:6]}_{item['type'].replace(' ', '_')}.jpg"
            item_path = os.path.join(output_dir, item_filename)

            prompt = (
                f"Generate an IMAGE. Professional studio product photo of a {item['color']} {item['type']} on a clean white background. "
                f"Minimalist, evenly lit, high resolution. Return only the image, no text. For {age_group} {gender}. Realistic."
            )

            t0 = time.time()
            path = self._generate_single_image(
                prompt,
                item_path,
                source_image_path=None,  # keep reference image ONLY for flat lay to reduce payload
            )
            elapsed = time.time() - t0
            print(f"⏱️  Item {i + 1}/{len(items)} ({item.get('type', 'item')}): {elapsed:.2f}s")
            if path:
                results["individual_items"].append(path)

            # Throttle between requests
            time.sleep(per_request_delay)

        # 2. Generate Combined Flat Lay:
        #    use the previously generated item images + (optionally) the source image,
        #    similar to the composition logic in `img_generator.py`.
        # flat_lay_prompt = self.outfit_to_flatlay_prompt(outfit_data, outfit_index)
        # flat_lay_path = os.path.join(
        #     output_dir, f"combined_flatlay_{uuid.uuid4().hex[:6]}.png"
        # )

        # t_flatlay_start = time.time()
        # try:
        #     content_parts = []

        #     # 1. Add the user's source image FIRST so the model treats it as the anchor item that MUST appear
        #     if source_image_path and os.path.exists(source_image_path):
        #         print(f"Including source image (user's item): {source_image_path}")
        #         img_path = Path(source_image_path)
        #         mime = (
        #             "image/jpeg"
        #             if img_path.suffix.lower() in [".jpg", ".jpeg"]
        #             else "image/png"
        #         )
        #         content_parts.append(
        #             {
        #                 "inline_data": {
        #                     "mime_type": mime,
        #                     "data": img_path.read_bytes(),
        #                 }
        #             }
        #         )

        #     # 2. Add all generated individual item images
        #     for img_path_str in results["individual_items"]:
        #         img_path = Path(img_path_str)
        #         if not img_path.exists():
        #             continue
        #         mime = (
        #             "image/jpeg"
        #             if img_path.suffix.lower() in [".jpg", ".jpeg"]
        #             else "image/png"
        #         )
        #         content_parts.append(
        #             {
        #                 "inline_data": {
        #                     "mime_type": mime,
        #                     "data": img_path.read_bytes(),
        #                 }
        #             }
        #         )

        #     # 3. Prompt: ALL images must appear; source image unchanged
        #     num_images = len(content_parts)
        #     user_item_instruction = (
        #         " The FIRST image is the user's actual clothing item (source image). You MUST include it in the flat lay EXACTLY as provided: do not redraw, alter, or omit it. "
        #         if content_parts and source_image_path and os.path.exists(source_image_path)
        #         else " "
        #     )
        #     content_parts.append(
        #         flat_lay_prompt
        #         + user_item_instruction
        #         + f" You have been given {num_images} image(s). EVERY ONE of these {num_images} images MUST appear in the flat lay — do not omit, skip, or drop any image. "
        #         "Arrange ALL the provided product shots into a cohesive fashion flat lay on a white background. "
        #         "Display each item SEPARATELY: do NOT layer, stack, or place any item on top of another. "
        #         "Each piece must have its own clear space with visible gaps between items. "
        #         "Return only the image, no text."
        #     )

        #     flat_lay_result = ""
        #     if content_parts:
        #         response = self.model.generate_content(content_parts)

        #         image_bytes = None
        #         if response.candidates and response.candidates[0].content.parts:
        #             for part in response.candidates[0].content.parts:
        #                 if hasattr(part, "inline_data") and part.inline_data:
        #                     image_bytes = part.inline_data.data
        #                     break
        #                 if hasattr(part, "blob") and part.blob:
        #                     image_bytes = part.blob.data
        #                     break

        #         if image_bytes:
        #             with open(flat_lay_path, "wb") as f:
        #                 f.write(image_bytes)
        #             if os.path.getsize(flat_lay_path) > 0:
        #                 print(f"✅ Successfully saved flat lay → {flat_lay_path}")
        #                 flat_lay_result = flat_lay_path

        #     results["flat_lay"] = flat_lay_result
        #     elapsed_flatlay = time.time() - t_flatlay_start
        #     print(f"⏱️  Flat lay (outfit {outfit_index + 1}): {elapsed_flatlay:.2f}s")

        # except Exception as e:
        #     print(f"❌ Flat lay composition failed: {e}")
        #     print(f"⏱️  Flat lay (outfit {outfit_index + 1}) failed after {time.time() - t_flatlay_start:.2f}s")

        return results

    def outfit_to_flatlay_prompt(self, outfit_data: dict, outfit_index: int = 0):
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        item_desc = ", ".join([f"{i['color']} {i['type']}" for i in items])
        return (
            f"A realistic fashion flat lay. Overhead view including {item_desc}. "
            f"Each item displayed separately with space between them, no overlapping. White background."
        )

    def generate_all_outfits(
        self,
        outfit_data: dict,
        output_dir: str = ".",
        source_image_path: str | None = None,
        per_request_delay: float = 1.5,
    ) -> list[dict]:
        """Generate flat lays and individual item images for all outfits.
        Returns list of dicts: [{"flat_lay": path, "individual_items": [path, ...]}, ...]."""
        os.makedirs(output_dir, exist_ok=True)
        results = []
        outfits = outfit_data.get("outfits", [])
        t_total_start = time.time()
        for i in range(len(outfits)):
            t_suite_start = time.time()
            print(f"\n⏱️  --- Outfit {i + 1}/{len(outfits)} ---")
            result = self.generate_full_suite(
                outfit_data,
                outfit_index=i,
                output_dir=output_dir,
                source_image_path=source_image_path,
                per_request_delay=per_request_delay,
            )
            elapsed_suite = time.time() - t_suite_start
            print(f"⏱️  Outfit {i + 1} total (items + flat lay): {elapsed_suite:.2f}s")
            results.append({
                "flat_lay": result.get("flat_lay") or "",
                "individual_items": result.get("individual_items") or [],
            })
        elapsed_total = time.time() - t_total_start
        print(f"\n⏱️  generate_all_outfits TOTAL: {elapsed_total:.2f}s for {len(outfits)} outfit(s)")
        return results