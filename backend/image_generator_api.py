# image_generator_api.py

import os
import base64
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
            raise ValueError("❌ GOOGLE_API_KEY not found in environment variables")

        genai.configure(api_key=self.api_key)

        # Gemini model (update if Google provides a dedicated image model)
        self.model = genai.GenerativeModel("gemini-2.5-flash-image")

        print("✅ Gemini API ready")

    def outfit_to_flatlay_prompt(self, outfit_data: dict, outfit_index: int = 0):
        outfits = outfit_data.get("outfits", [])
        if not outfits:
            return ""

        outfit = outfits[outfit_index]
        items = outfit.get("items", [])
        style_title = outfit.get("style_title", "")
        occasion = outfit.get("occasion", "casual")
        age_group = outfit.get("age_group")
        gender = outfit.get("gender")

        item_descriptions = [
            f"{item['color']} {item['type']}" for item in items
        ]
        outfit_desc = ", ".join(item_descriptions)

        prompt = (
            f"Generate a realistic minimalist fashion flat lay image. "
            f"Overhead view of {outfit_desc}. "
            f"White background. Soft studio lighting. "
            f"For {age_group} {gender}. "
            f"{style_title} {occasion} aesthetic. "
            f"Editorial product photography. "
            f"No people. No mannequins."
        )

        return prompt

    def generate(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_path: str = "outfit_flatlay.png",
        source_image_path: str | None = None,
    ) -> str:

        prompt = self.outfit_to_flatlay_prompt(outfit_data, outfit_index)

        if not prompt:
            print("❌ No outfit data")
            return ""

        outfit_name = outfit_data.get("outfits", [{}])[outfit_index].get("style_title", "outfit")
        print(f"🎨 Generating flat lay for: {outfit_name}")
        print(f"📝 Prompt: {prompt}")

        try:
            # If we have the original uploaded item image, send it as context
            # so Gemini can incorporate it into the generated flat lay.
            if source_image_path is not None:
                base_image_bytes = Path(source_image_path).read_bytes()
                response = self.model.generate_content(
                    [
                        {
                            "inline_data": {
                                "data": base_image_bytes,
                                "mime_type": "image/png",
                            }
                        },
                        prompt,
                    ]
                )
            else:
                # Text-only generation
                response = self.model.generate_content(prompt)
            # Gemini returns images in the 'parts' of the first candidate
            candidate = response.candidates[0]
            image_bytes = None

            for part in candidate.content.parts:
                # Check for the 'inline_data' or 'blob' attribute
                if part.inline_data:
                    image_bytes = part.inline_data.data 
                    # Note: The SDK often returns bytes directly here, 
                    # so base64.b64decode might not be necessary if it's already bytes.
                    break
            
            if not image_bytes:
                print("❌ No image data found in response parts")
                return ""

            # Ensure we are writing actual bytes
            with open(output_path, "wb") as f:
                f.write(image_bytes)
        
            print(f"✅ Saved → {output_path}")
            return output_path

        except Exception as e:
            print(f"❌ Gemini API failed: {e}")
            return ""

    def generate_all_outfits(
        self,
        outfit_data: dict,
        output_dir: str = ".",
        source_image_path: str | None = None,
    ):
        os.makedirs(output_dir, exist_ok=True)

        paths = []
        outfits = outfit_data.get("outfits", [])

        for i, outfit in enumerate(outfits):
            occasion = outfit.get("occasion", f"outfit_{i}").replace(" ", "_")
            output_path = f"{output_dir}/{occasion}_{uuid.uuid4().hex}_flatlay.png"
            path = self.generate(
                outfit_data,
                outfit_index=i,
                output_path=output_path,
                source_image_path=source_image_path,
            )
            paths.append(path)

        return paths