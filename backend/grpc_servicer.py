"""
gRPC servicer for the Stylist service. Runs the full pipeline and streams progress.
"""
import json
import uuid
from pathlib import Path

import grpc

# Generated protobuf and gRPC (run via backend.grpc_server so generated/ is on path)
import stylist_pb2
import stylist_pb2_grpc

from db import SessionLocal
from models import Outfit, OutfitImage, OutfitItem
from image_generator_api_advanced import OutfitImageGenerator
from item_captioning import analyze_wardrobe_item
from outfit_suggestion import generate_outfit_suggestions

from routers.api import (
    UPLOAD_DIR,
    OUTPUT_DIR,
    get_image_generator,
    _occasions_from_attributes,
)


class StylistServicer(stylist_pb2_grpc.StylistServicer):
    """Implements RunFullPipeline with real progress streaming."""

    def RunFullPipeline(self, request, context):
        """Run analyze → suggest → generate images; yield progress then final result."""
        image_bytes = request.image or b""
        filename = request.filename or "image.jpg"
        occasions_str = request.occasions or ""

        def yield_progress(percent: int, message: str = ""):
            resp = stylist_pb2.PipelineProgressResponse(
                progress=stylist_pb2.Progress(percent=percent, message=message)
            )
            return resp

        def yield_result(result_dict: dict):
            return stylist_pb2.PipelineProgressResponse(
                result=stylist_pb2.Result(result_json=json.dumps(result_dict))
            )

        try:
            yield yield_progress(5, "Saving image…")

            ext = Path(filename).suffix or ".jpg"
            unique_name = f"{uuid.uuid4()}{ext}"
            filepath = UPLOAD_DIR / unique_name
            filepath.write_bytes(image_bytes)

            yield yield_progress(15, "Analyzing item…")
            attributes = analyze_wardrobe_item(str(filepath))
            if attributes.get("error") == "no_garment":
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(
                    attributes.get("message", "The image does not appear to contain a clothing item.")
                )
                return

            yield yield_progress(35, "Suggesting outfits…")
            if occasions_str.strip():
                occasions_list = [o.strip() for o in occasions_str.split(",") if o.strip()]
            else:
                occasions_list = _occasions_from_attributes(attributes)
            outfit_data = generate_outfit_suggestions(
                item_attributes=attributes,
                occasions=occasions_list,
            )
            outfits = outfit_data.get("outfits", []) or []
            n_outfits = len(outfits)

            generator: OutfitImageGenerator = get_image_generator()
            image_results = []
            for i in range(n_outfits):
                pct = 40 + int((i + 1) / n_outfits * 50) if n_outfits else 90
                yield yield_progress(pct, f"Generating outfit {i + 1}/{n_outfits}…")
                result = generator.generate_full_suite(
                    outfit_data,
                    outfit_index=i,
                    output_dir=str(OUTPUT_DIR),
                    source_image_path=str(filepath),
                )
                image_results.append({
                    "flat_lay": result.get("flat_lay") or "",
                    "individual_items": result.get("individual_items") or [],
                })

            flatlay_urls = []
            for res in image_results:
                flat_lay = res.get("flat_lay")
                if flat_lay:
                    flatlay_urls.append(f"/api/image/{Path(flat_lay).name}")

            for idx, outfit in enumerate(outfits):
                items = outfit.get("items", [])
                if idx < len(image_results):
                    item_paths = image_results[idx].get("individual_items") or []
                    for j, item in enumerate(items):
                        if j < len(item_paths) and item_paths[j]:
                            item["image_url"] = f"/api/image/{Path(item_paths[j]).name}"

            yield yield_progress(95, "Saving…")

            session = SessionLocal()
            try:
                for idx, outfit in enumerate(outfits):
                    db_outfit = Outfit(
                        occasion=outfit.get("occasion", ""),
                        style_title=outfit.get("style_title", ""),
                        style_notes=outfit.get("style_notes", ""),
                        color_palette=",".join(outfit.get("color_palette", [])),
                        source_image_path=str(filepath),
                        attributes=attributes,
                    )
                    session.add(db_outfit)
                    session.flush()
                    if idx < len(image_results) and image_results[idx].get("flat_lay"):
                        session.add(
                            OutfitImage(
                                outfit_id=db_outfit.id,
                                kind="flatlay",
                                image_path=image_results[idx]["flat_lay"],
                            )
                        )
                    item_fs_paths = (
                        image_results[idx].get("individual_items") or []
                        if idx < len(image_results) else []
                    )
                    for j, item in enumerate(outfit.get("items", [])):
                        session.add(
                            OutfitItem(
                                outfit_id=db_outfit.id,
                                category=item.get("category"),
                                color=item.get("color"),
                                type=item.get("type"),
                                description=item.get("description"),
                                likely_owned=bool(item.get("likely_owned")),
                                shopping_keywords=item.get("shopping_keywords"),
                                image_path=item_fs_paths[j] if j < len(item_fs_paths) else None,
                            )
                        )
                session.commit()
            except Exception as e:
                session.rollback()
                import logging
                logging.getLogger("uvicorn.error").warning("Could not persist to database: %s", e)
            finally:
                session.close()

            first_image_url = flatlay_urls[0] if flatlay_urls else None
            result_payload = {
                "success": True,
                "image_id": unique_name,
                "attributes": attributes,
                "outfits": outfit_data,
                "image_url": first_image_url,
                "flatlay_image_urls": flatlay_urls,
            }
            yield yield_progress(100, "Done")
            yield yield_result(result_payload)

        except grpc.RpcError:
            raise
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise
