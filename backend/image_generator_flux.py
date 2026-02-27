# image_generator.py
import torch
from diffusers import AutoPipelineForText2Image, Flux2Pipeline
import json
import os

class OutfitImageGenerator:
    def __init__(self, model_id: str = "stabilityai/sdxl-turbo"): #black-forest-labs/FLUX.1-schnell - 33GB, black-forest-labs/FLUX.2-Klein-4B - 16GB, stabilityai/sdxl-turbo - 5GB
        print("🔄 Loading SDXL model...")
        self.pipe = AutoPipelineForText2Image.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            variant="fp16"
        )
        self.pipe.to("mps")
        print("✅ SDXL model loaded")

    def outfit_to_flatlay_prompt(self, outfit_data: dict, outfit_index: int = 0) -> tuple[str, str]:
        outfits = outfit_data.get("outfits", [])
        if not outfits:
            return "", ""

        outfit = outfits[outfit_index]
        items = outfit.get("items", [])
        palette = ", ".join(outfit.get("color_palette", []))
        style_title = outfit.get("style_title", "")
        occasion = outfit.get("occasion", "casual")

        # Build item descriptions from your JSON structure
        item_descriptions = []
        for item in items:
            item_descriptions.append(f"{item['color']} {item['type']}")
        outfit_desc = ", ".join(item_descriptions)

        prompt = f"""flat lay fashion photography, overhead bird's eye view shot,
{outfit_desc},
clothing and accessories neatly arranged on a clean white background,
items laid flat without any person or mannequin,
color palette {palette},
{style_title} {occasion} aesthetic,
minimalist composition with generous white space between items,
soft diffused natural lighting, no shadows,
professional fashion editorial flat lay,
ultra sharp focus, 4k product photography"""

        negative_prompt = """person, human body, mannequin, hanger, model,
3d render, cartoon, illustration,
dark background, cluttered, overlapping items,
blurry, out of focus, low quality, watermark, text,
wrinkled fabric, bad composition, distorted items"""

        return prompt, negative_prompt

    def generate(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_path: str = "outfit_flatlay.png",
        width: int = 512,
        height: int = 512,
        num_inference_steps: int = 2,  
        guidance_scale: float = 0.0,   
    ) -> str:

        prompt, negative_prompt = self.outfit_to_flatlay_prompt(outfit_data, outfit_index)

        if not prompt:
            print("❌ No outfit data to generate from")
            return ""

        outfit_name = outfit_data.get("outfits", [{}])[outfit_index].get("style_title", "outfit")
        print(f"🎨 Generating flat lay for: {outfit_name}")
        print(f"📝 Prompt: {prompt[:100]}...")

        image = self.pipe(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            max_sequence_length=512,
        ).images[0]

        image.save(output_path)
        print(f"✅ Saved → {output_path}")
        return output_path

    def generate_all_outfits(self, outfit_data: dict, output_dir: str = ".") -> list[str]:
        """Generate flat lay for every occasion in outfit suggestions."""
        import os
        os.makedirs(output_dir, exist_ok=True)

        paths = []
        outfits = outfit_data.get("outfits", [])

        for i, outfit in enumerate(outfits):
            occasion = outfit.get("occasion", f"outfit_{i}").replace(" ", "_")
            output_path = f"{output_dir}/{occasion}_flatlay.png"
            path = self.generate(outfit_data, outfit_index=i, output_path=output_path)
            paths.append(path)

        return paths