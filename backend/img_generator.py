import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import uuid

class OutfitImageGenerator:
    def __init__(self):
        print("🔄 Initializing Gemini Image Generator...")
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GOOGLE_API_KEY not found")

        genai.configure(api_key=self.api_key)
        
        self.model = genai.GenerativeModel("gemini-2.5-flash-image") 
        print("✅ Gemini API ready")

    def _generate_single_image(self, prompt: str, output_path: str, source_image_path: str = None) -> str:
        """Internal helper with strict error checking and binary safety."""
        try:
            content_parts = []
            
            # Add source image context if it exists
            if source_image_path and os.path.exists(source_image_path):
                img_path = Path(source_image_path)
                content_parts.append({
                    "mime_type": "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png",
                    "data": img_path.read_bytes()
                })
            
            content_parts.append(prompt)

            # Important: Ask the model to generate an image specifically
            response = self.model.generate_content(content_parts)
            
            # Check if response actually has content
            if not response.candidates or not response.candidates[0].content.parts:
                print(f"⚠️ No content returned for: {prompt[:30]}...")
                return ""

            image_bytes = None
            for part in response.candidates[0].content.parts:
                # The data is usually in 'inline_data' for generated images
                if hasattr(part, 'inline_data') and part.inline_data:
                    image_bytes = part.inline_data.data
                # Some versions use 'blob'
                elif hasattr(part, 'blob') and part.blob:
                    image_bytes = part.blob.data

            if not image_bytes:
                # If we get here, the model likely replied with TEXT instead of an IMAGE
                print(f"❌ Model replied with text instead of an image. Response text: {response.text[:100]}")
                return ""

            # Write in Binary Mode ('wb') - only if we have bytes
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            
            # Final check: is the file size greater than 0?
            if os.path.getsize(output_path) > 0:
                print(f"✅ Successfully saved → {output_path}")
                return output_path
            else:
                print(f"❌ File saved but is empty: {output_path}")
                return ""

        except Exception as e:
            print(f"❌ API Error: {e}")
            return ""

    def generate_full_suite(self, outfit_data: dict, outfit_index: int = 0, output_dir: str = "outfits", source_image_path: str = None) -> dict:
        os.makedirs(output_dir, exist_ok=True)
        print(f"outfit_data: {outfit_data}")
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        gender = outfit_data.get("gender_context", [])
        age_group = outfit_data.get("gender_context", [])
        
        generated_paths = []
        item_image_paths = []

        # 1. Individual Items
        for i, item in enumerate(items):
            filename = f"item_{uuid.uuid4().hex}_{item['type'].replace(' ', '_')}.png"
            path = os.path.join(output_dir, filename)
            prompt = f"Product shot of a {item['color']} {item['type']} on white background. {item['description']} for {age_group} {gender}. Realistic."
            
            res = self._generate_single_image(prompt, path, source_image_path)
            if res:
                generated_paths.append(res)
                item_image_paths.append(res)

        # 2. Combined Flat Lay built from already generated item images
        fl_path = os.path.join(output_dir, f"flatlay_{uuid.uuid4().hex[:6]}.png")
        fl_prompt = self.outfit_to_flatlay_prompt(outfit_data, outfit_index)

        # Build content from per-item product shots instead of a totally new hallucinated image
        try:
            content_parts = []
            for img_path_str in item_image_paths:
                img_path = Path(img_path_str)
                if not img_path.exists():
                    continue
                content_parts.append({
                    "mime_type": "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png",
                    "data": img_path.read_bytes(),
                })

            # Fallback: if for some reason no item images were generated, just use the source image (if any)
            if not content_parts and source_image_path and os.path.exists(source_image_path):
                img_path = Path(source_image_path)
                content_parts.append({
                    "mime_type": "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png",
                    "data": img_path.read_bytes(),
                })

            content_parts.append(
                fl_prompt
                + " Arrange ONLY the provided product shots into a cohesive fashion flat lay, white background."
            )

            if content_parts:
                response = self.model.generate_content(content_parts)

                image_bytes = None
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            image_bytes = part.inline_data.data
                        elif hasattr(part, "blob") and part.blob:
                            image_bytes = part.blob.data

                if image_bytes:
                    with open(fl_path, "wb") as f:
                        f.write(image_bytes)

                    if os.path.getsize(fl_path) > 0:
                        print(f"✅ Successfully saved flat lay → {fl_path}")
                        generated_paths.append(fl_path)
        except Exception as e:
            print(f"❌ Flat lay composition failed: {e}")

        return generated_paths

    def outfit_to_flatlay_prompt(self, outfit_data: dict, outfit_index: int = 0):
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        desc = ", ".join([f"{i['color']} {i['type']}" for i in items])
        return f"Fashion flat lay overhead view of {desc}. High quality, white background."