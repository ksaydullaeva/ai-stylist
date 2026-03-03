# image_generator_sdxl_fashion.py
# Local image generator using shindeaditya/sdxl-fashion.
# LoRA adapter fine-tuned on wbensvage/clothes_desc, base: stabilityai/stable-diffusion-xl-base-1.0.
# Uses madebyollin/sdxl-vae-fp16-fix (required — was used during training).
# Runs on Apple Silicon via MPS; falls back to CUDA then CPU.
#
# Requires:
#   pip install diffusers transformers accelerate torch torchvision safetensors
#
# Notes:
#   - Native SDXL resolution is 1024×1024; smaller sizes reduce quality.
#   - guidance_scale=7.5 and ~30 steps give the best quality/speed trade-off.
#   - The model is already fashion-focused so prompts don't need heavy style keywords.
#   - Text-encoder LoRA was enabled during training (loaded automatically via load_lora_weights).

import os
import time
import uuid

import torch
from diffusers import AutoencoderKL, StableDiffusionXLPipeline


BASE_MODEL      = "stabilityai/stable-diffusion-xl-base-1.0"
LORA_MODEL      = "shindeaditya/sdxl-fashion"
VAE_MODEL       = "madebyollin/sdxl-vae-fp16-fix"   # required — used during LoRA training

IMAGE_SIZE           = 512   # SDXL native - 1024; drop to 768 to trade quality for speed
NUM_INFERENCE_STEPS  = 20
GUIDANCE_SCALE       = 6.0


def _get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class OutfitImageGenerator:
    """
    Fashion product-photo generator backed by shindeaditya/sdxl-fashion.

    The LoRA was trained on wbensvage/clothes_desc, so prompts in the form
    "a photo of <color> <garment-type> …" work well out of the box.
    """

    def __init__(self) -> None:
        device = _get_device()
        print(f"Loading sdxl-fashion pipeline on {device} …")

        # The special VAE must match what was used during LoRA training.
        dtype = torch.float16
        vae = AutoencoderKL.from_pretrained(VAE_MODEL, torch_dtype=dtype)

        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            BASE_MODEL,
            vae=vae,
            torch_dtype=dtype,
            variant="fp16",
            use_safetensors=True,
        ).to(device)

        # Load fashion LoRA (covers both UNet and text-encoder weights).
        self.pipe.load_lora_weights(LORA_MODEL)
        self.pipe.fuse_lora()

        # Recommended for MPS: reduce peak memory usage.
        if device == "mps":
            self.pipe.enable_attention_slicing()

        self.device = device
        print("sdxl-fashion ready")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _item_prompt(self, item: dict, gender: str, age_group: str) -> str:
        """Build a prompt suited to the fashion LoRA's training distribution."""
        color   = item.get("color", "")
        style   = item.get("style", "")
        type_   = item.get("type", "garment")
        desc    = f"{color} {style} {type_}".strip()
        neg_ctx = f"{age_group} {gender}" if age_group or gender else ""
        return (
            f"a photo of {desc}, fashion product photo, "
            f"studio white background, soft even lighting, "
            f"isolated clothing item{', ' + neg_ctx if neg_ctx else ''}, "
            "high detail, photorealistic, no mannequin, no hanger, no model, realistic product only"
        )

    @staticmethod
    def _negative_prompt() -> str:
        return (
            "blurry, low quality, deformed, disfigured, extra limbs, "
            "text, watermark, logo, background clutter, human face, mannequin"
        )

    def _generate_single_image(self, prompt: str, output_path: str) -> str:
        """Run the diffusion pipeline for one prompt and save to output_path."""
        try:
            t0 = time.time()
            print(f"Generating image for prompt: {prompt}")
            result = self.pipe(
                prompt=prompt,
                negative_prompt=self._negative_prompt(),
                num_inference_steps=NUM_INFERENCE_STEPS,
                guidance_scale=GUIDANCE_SCALE,
                width=IMAGE_SIZE,
                height=IMAGE_SIZE,
            )
            print(f"    [diffusion: {time.time() - t0:.2f}s]")

            img = result.images[0]
            img.save(output_path)
            print(f"Saved → {output_path}")
            return output_path
        except Exception as e:
            print(f"Generation failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # Public API  (matches the interface used by services/pipeline.py)
    # ------------------------------------------------------------------

    def generate_full_suite(
        self,
        outfit_data: dict,
        outfit_index: int = 0,
        output_dir: str = "outfits",
        source_image_path: str | None = None,
    ) -> dict:
        """Generate individual item images for one outfit.

        source_image_path is accepted for API compatibility but not used
        (local text-to-image model — no image conditioning).

        Returns:
            {"individual_items": [saved_path, ...]}
        """
        os.makedirs(output_dir, exist_ok=True)
        outfit    = outfit_data.get("outfits", [])[outfit_index]
        items     = outfit.get("items", [])
        gender    = outfit_data.get("gender_context", "")
        age_group = outfit_data.get("age_group", "adult")
        individual_items: list[str] = []

        for i, item in enumerate(items):
            filename = f"item_{uuid.uuid4().hex[:8]}_{item['type'].replace(' ', '_')}.png"
            out_path = os.path.join(output_dir, filename)
            prompt   = self._item_prompt(item, gender, age_group)
            t0       = time.time()
            path     = self._generate_single_image(prompt, out_path)
            print(f"Item {i + 1}/{len(items)} ({item.get('type', '')}): {time.time() - t0:.2f}s")
            if path:
                individual_items.append(path)

        return {"individual_items": individual_items}

    def generate_all_outfits(
        self,
        outfit_data: dict,
        output_dir: str = ".",
        source_image_path: str | None = None,
    ) -> list[dict]:
        """Generate item images for every outfit in outfit_data.

        Returns:
            [{"individual_items": [...]}, ...]
        """
        os.makedirs(output_dir, exist_ok=True)
        outfits  = outfit_data.get("outfits", [])
        t_total  = time.time()
        results: list[dict] = []

        for i in range(len(outfits)):
            print(f"\n--- Outfit {i + 1}/{len(outfits)} ---")
            t0     = time.time()
            result = self.generate_full_suite(
                outfit_data,
                outfit_index=i,
                output_dir=output_dir,
                source_image_path=source_image_path,
            )
            print(f"Outfit {i + 1} total: {time.time() - t0:.2f}s")
            results.append(result)

        print(f"\nAll outfits total: {time.time() - t_total:.2f}s for {len(outfits)} outfit(s)")
        return results
