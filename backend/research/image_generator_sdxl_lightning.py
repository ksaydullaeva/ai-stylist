# image_generator.py
# Local image generator using SDXL-Lightning (4-step distilled diffusion model).
# Runs on Apple Silicon via MPS; falls back to CPU when MPS is unavailable.
#
# Requires: pip install diffusers transformers accelerate torch torchvision
# Model:    stabilityai/sdxl-lightning-4step (ByteDance distillation)
#
# This approach was abandoned in favour of the Gemini API generators because:
# - SDXL-Lightning produces plausible but generic product images
# - No way to condition on user's source garment
# - MPS memory limits caused OOM on larger batch sizes

import os
import time
import uuid

import torch
from diffusers import AutoencoderKL, EulerDiscreteScheduler, StableDiffusionXLPipeline


SDXL_LIGHTNING_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
SDXL_LIGHTNING_LORA  = "ByteDance/SDXL-Lightning"
SDXL_LIGHTNING_LORA_WEIGHTS = "sdxl_lightning_4step_lora.safetensors"
VAE_MODEL = "madebyollin/sdxl-vae-fp16-fix"  # fewer artifacts than default SDXL VAE

IMAGE_SIZE = 512  # 512 fits MPS ~9GB; use 768 on 16GB+ (enable slicing below)
NUM_INFERENCE_STEPS = 4
GUIDANCE_SCALE = 0.0  # Lightning requires guidance_scale=0


def _get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class OutfitImageGenerator:
    def __init__(self):
        print("🔄 Loading SDXL-Lightning pipeline…")
        device = _get_device()
        print(f"   Using device: {device}")

        dtype = torch.float16
        vae = AutoencoderKL.from_pretrained(VAE_MODEL, torch_dtype=dtype)
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            SDXL_LIGHTNING_MODEL,
            vae=vae,
            torch_dtype=dtype,
            variant="fp16",
        ).to(device)

        self.pipe.load_lora_weights(
            SDXL_LIGHTNING_LORA,
            weight_name=SDXL_LIGHTNING_LORA_WEIGHTS,
        )
        self.pipe.fuse_lora()

        self.pipe.scheduler = EulerDiscreteScheduler.from_config(
            self.pipe.scheduler.config,
            timestep_spacing="trailing",
        )

        # Reduce MPS memory use to avoid OOM (max ~9GB on many Apple Silicon Macs).
        if device == "mps":
            self.pipe.enable_attention_slicing()
            self.pipe.enable_vae_slicing()
            self.pipe.enable_vae_tiling()

        self.device = device
        print("✅ SDXL-Lightning ready")

    @staticmethod
    def _negative_prompt() -> str:
        return "blurry, low quality, distorted, noisy, deformed, text, watermark"

    def _generate_single_image(self, prompt: str, output_path: str) -> str:
        """Run the diffusion pipeline for one prompt and save to output_path."""
        try:
            t0 = time.time()
            result = self.pipe(
                prompt=prompt,
                negative_prompt=self._negative_prompt(),
                num_inference_steps=NUM_INFERENCE_STEPS,
                guidance_scale=GUIDANCE_SCALE,
                width=IMAGE_SIZE,
                height=IMAGE_SIZE,
            )
            elapsed = time.time() - t0
            print(f"    [diffusion: {elapsed:.2f}s]")

            img = result.images[0]
            img.save(output_path)
            print(f"✅ Saved → {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            return ""

    def _item_prompt(self, item: dict, gender: str, age_group: str) -> str:
        return (
            f"Professional fashion product photo, {item['color']} {item['type']}, "
            f"studio white background, soft even lighting, {age_group} {gender} style, "
            "no text, no model, isolated item, photorealistic, high detail, sharp focus, clean product shot"
        )

    def generate_full_suite(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_dir: str = "outfits",
        source_image_path: str | None = None,
    ) -> dict:
        """Generate individual item images for one outfit.
        source_image_path is accepted for API compatibility but ignored (local model)."""
        os.makedirs(output_dir, exist_ok=True)
        outfit = outfit_data.get("outfits", [])[outfit_index]
        items = outfit.get("items", [])
        gender = outfit_data.get("gender_context", "adult")
        age_group = outfit_data.get("age_group", "adult")
        results = {"individual_items": [], "flat_lay": ""}

        for i, item in enumerate(items):
            filename = f"item_{uuid.uuid4().hex[:6]}_{item['type'].replace(' ', '_')}.png"
            out_path = os.path.join(output_dir, filename)
            prompt = self._item_prompt(item, gender, age_group)
            t0 = time.time()
            path = self._generate_single_image(prompt, out_path)
            print(f"⏱️  Item {i + 1}/{len(items)} ({item.get('type', '')}): {time.time() - t0:.2f}s")
            if path:
                results["individual_items"].append(path)

        return results

    def generate_all_outfits(
        self,
        outfit_data: dict,
        output_dir: str = ".",
        source_image_path: str | None = None,
    ) -> list[dict]:
        """Generate item images for every outfit."""
        os.makedirs(output_dir, exist_ok=True)
        outfits = outfit_data.get("outfits", [])
        results = []
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
