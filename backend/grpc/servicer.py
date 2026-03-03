"""
gRPC servicer for the Stylist service.
Implements RunFullPipeline with streaming progress — mirrors the HTTP /full-pipeline-stream endpoint.
"""

import json
import uuid
from pathlib import Path

import grpc

# grpc/generated/ is added to sys.path by grpc/server.py before this module is imported
import stylist_pb2       # noqa: E402
import stylist_pb2_grpc  # noqa: E402

from ai.captioning import analyze_wardrobe_item
from ai.suggestion import generate_outfit_suggestions
from repositories.outfit import persist_outfits
from services.pipeline import (
    UPLOAD_DIR,
    OUTPUT_DIR,
    get_image_generator,
    occasions_from_attributes,
    attach_image_urls,
)


class StylistServicer(stylist_pb2_grpc.StylistServicer):
    """Implements RunFullPipeline with real progress streaming."""

    def RunFullPipeline(self, request, context):
        """Analyze → suggest → generate images; yield progress then final result."""
        image_bytes: bytes = request.image or b""
        filename: str = request.filename or "image.jpg"
        occasions_str: str = request.occasions or ""

        def progress(percent: int, message: str = ""):
            return stylist_pb2.PipelineProgressResponse(
                progress=stylist_pb2.Progress(percent=percent, message=message)
            )

        def result(payload: dict):
            return stylist_pb2.PipelineProgressResponse(
                result=stylist_pb2.Result(result_json=json.dumps(payload))
            )

        try:
            yield progress(5, "Saving image…")
            filepath = UPLOAD_DIR / f"{uuid.uuid4()}{Path(filename).suffix or '.jpg'}"
            filepath.write_bytes(image_bytes)

            yield progress(15, "Analyzing item…")
            attributes = analyze_wardrobe_item(str(filepath))
            if attributes.get("error") == "no_garment":
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(attributes.get("message", "No garment detected."))
                return

            yield progress(35, "Suggesting outfits…")
            occasions_list = (
                [o.strip() for o in occasions_str.split(",") if o.strip()]
                if occasions_str.strip()
                else occasions_from_attributes(attributes)
            )
            outfit_data = generate_outfit_suggestions(
                item_attributes=attributes,
                occasions=occasions_list,
            )
            outfits = outfit_data.get("outfits", []) or []
            n_outfits = len(outfits)

            generator = get_image_generator()
            image_results = []
            for i in range(n_outfits):
                pct = 40 + int((i + 1) / n_outfits * 50) if n_outfits else 90
                yield progress(pct, f"Generating outfit {i + 1}/{n_outfits}…")
                res = generator.generate_full_suite(
                    outfit_data,
                    outfit_index=i,
                    output_dir=str(OUTPUT_DIR),
                    source_image_path=str(filepath),
                )
                image_results.append({
                    "individual_items": res.get("individual_items") or [],
                })

            attach_image_urls(outfits, image_results)

            yield progress(95, "Saving…")
            persist_outfits(outfits, image_results, filepath, attributes)

            yield progress(100, "Done")
            yield result({
                "success": True,
                "image_id": filepath.name,
                "attributes": attributes,
                "outfits": outfit_data,
            })

        except grpc.RpcError:
            raise
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise
