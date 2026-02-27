import torch
from diffusers import StableDiffusionXLPipeline, UNet2DConditionModel, EulerDiscreteScheduler
import json
import os
import time

class OutfitImageGenerator:
    def __init__(self, model_id: str = "stabilityai/stable-diffusion-xl-base-1.0"):
        print("🔄 Loading SDXL Lightning 4-step model...")
        start = time.time()
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16
        ).to("mps")

        # 2️⃣ Load Lightning UNet weights
        unet = UNet2DConditionModel.from_pretrained(
            "ByteDance/SDXL-Lightning",
            subfolder="unet",
            torch_dtype=torch.float16
        )

        pipe.unet = unet

        # 3️⃣ Set correct scheduler
        pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)

        self.pipe.enable_attention_slicing()
        print(f"✅ Model loaded in {time.time() - start:.2f}s")

    def outfit_to_flatlay_prompt(self, outfit_data: dict, outfit_index: int = 0) -> str:
        outfits = outfit_data.get("outfits", [])
        if not outfits:
            return ""

        outfit = outfits[outfit_index]
        items = outfit.get("items", [])
        palette = ", ".join(outfit.get("color_palette", []))
        style_title = outfit.get("style_title", "")
        occasion = outfit.get("occasion", "casual")

        item_descriptions = [f"{item['color']} {item['type']}" for item in items]
        outfit_desc = ", ".join(item_descriptions)

        # SDXL Lightning performs best with descriptive, high-quality tags
        prompt = (
            f"Professional fashion flat lay, overhead view, {outfit_desc}, "
            f"clean white background, minimalist composition, "
            f"color palette: {palette}, {style_title} {occasion} aesthetic, "
            f"soft studio lighting, high resolution, 8k"
        )
        
        return prompt

    def generate(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_path: str = "outfit_flatlay.png",
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 4,  # Lightning is designed for 4-8 steps
        guidance_scale: float = 0.0,   # IMPORTANT: Lightning usually works best with 0 guidance
    ) -> str:

        prompt = self.outfit_to_flatlay_prompt(outfit_data, outfit_index)

        if not prompt:
            print("❌ No outfit data to generate from")
            return ""

        outfit_name = outfit_data.get("outfits", [{}])[outfit_index].get("style_title", "outfit")
        print(f"🎨 Generating flat lay for: {outfit_name}")

        # Note: SDXL Lightning technically doesn't use negative prompts effectively 
        # at low steps/0 guidance, so we focus purely on the positive prompt.
        image = self.pipe(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale
        ).images[0]

        image.save(output_path)
        print(f"✅ Saved → {output_path}")
        return output_path

    def generate_all_outfits(self, outfit_data: dict, output_dir: str = "generated_outfits") -> list[str]:
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        outfits = outfit_data.get("outfits", [])

        for i, outfit in enumerate(outfits):
            occasion = outfit.get("occasion", f"outfit_{i}").lower().replace(" ", "_")
            output_path = os.path.join(output_dir, f"{occasion}_flatlay.png")
            path = self.generate(outfit_data, outfit_index=i, output_path=output_path)
            paths.append(path)

        return paths