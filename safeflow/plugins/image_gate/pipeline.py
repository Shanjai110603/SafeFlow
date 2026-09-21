"""Profile Image Safety Gate Pipeline.

Implements upload validation, EXIF orientation handling, dual-crop classification,
simulated known-bad hash checking, OCR explicit text checking, policy mapping,
perceptual hash computation (including mirror hashing), and zero-byte persistence for BLOCK.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
import imagehash
from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel, ConfigDict, Field
from safeflow.core.audit import AuditLogger
from safeflow.core.blob_store import ReviewBlobStore
from safeflow.core.config import PolicyPack
from safeflow.plugins.image_gate.classifier import (
    ImageSafetyClassifier,
    MockClassifier,
)

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
PIXEL_CAP = 25_000_000  # 25 megapixels decompression bomb guard

# Simulated known-bad perceptual hashes (mock CSAM/exploitative list for tests)
SIMULATED_KNOWN_BAD_HASHES = {
    "0000ffff0000ffff",
    "deadbeefdeadbeef",
    "bad0bad0bad0bad0"
}


class UnsupportedFormatError(ValueError):
    """Raised when an uploaded image format is not in the strict allowlist."""
    pass


class DecompressionBombError(ValueError):
    """Raised when an uploaded image exceeds the maximum permitted pixel count."""
    pass


class ImageSafetyResult(BaseModel):
    """Canonical result emitted by the image safety gate."""
    model_config = ConfigDict(extra="forbid")

    nudity_score: float = Field(..., ge=0.0, le=1.0, json_schema_extra={"visibility": "analyst"})
    explicit_score: float = Field(..., ge=0.0, le=1.0, json_schema_extra={"visibility": "analyst"})
    suggestive_score: float = Field(..., ge=0.0, le=1.0, json_schema_extra={"visibility": "analyst"})
    ocr_explicit_text: bool = Field(default=False, json_schema_extra={"visibility": "analyst"})
    known_bad_hash_match: bool = Field(default=False, json_schema_extra={"visibility": "analyst"})
    crop_used: Literal["full", "display_crop"] = Field(default="full", json_schema_extra={"visibility": "analyst"})
    backend_scores: dict[str, float] = Field(default_factory=dict, json_schema_extra={"visibility": "analyst"})
    model_name: str = Field(..., json_schema_extra={"visibility": "analyst"})
    model_version: str = Field(..., json_schema_extra={"visibility": "analyst"})
    decision: Literal["ALLOW", "ALLOW_TAGGED", "REVIEW", "BLOCK"]
    reasons: list[str] = Field(default_factory=list, json_schema_extra={"visibility": "analyst"})
    perceptual_hashes: dict[str, str] = Field(default_factory=dict, json_schema_extra={"visibility": "analyst"})
    applied_tags: list[str] = Field(default_factory=list, json_schema_extra={"visibility": "analyst"})


class ImageGatePipeline:
    """Executes the complete profile image safety gate pipeline."""

    def __init__(
        self,
        classifier: ImageSafetyClassifier | None = None,
        blob_store: ReviewBlobStore | None = None,
        audit_logger: AuditLogger | None = None
    ) -> None:
        self.classifier = classifier or MockClassifier()
        self.blob_store = blob_store or ReviewBlobStore()
        self.audit_logger = audit_logger or AuditLogger()

    def process(
        self,
        image_bytes: bytes,
        policy_pack: PolicyPack,
        actor_id: str = "anon_actor",
        media_id: str = "media_upload",
        simulate_ocr_explicit: bool = False
    ) -> ImageSafetyResult:
        """Process an uploaded image through all verification stages."""
        # 1. Validation & Hardening (Amendment 10)
        original_metadata, preprocessed_bytes, full_img = self._validate_and_preprocess(image_bytes)

        # 2. Compute perceptual hashes (pHash, dHash, wHash) & mirror pHash (Amendment 5, 6)
        hashes = self._compute_hashes(full_img)

        # 3. Known-bad hash check
        known_bad = hashes["phash"] in SIMULATED_KNOWN_BAD_HASHES

        # 4. Extract circular avatar display crop
        crop_bytes = self._extract_avatar_crop(full_img)

        # 5. Dual-crop classification
        classifier_error = False
        error_msg = ""
        try:
            full_res = self.classifier.classify(
                preprocessed_bytes,
                crop_kind="full",
                original_metadata=original_metadata
            )
            crop_res = self.classifier.classify(
                crop_bytes,
                crop_kind="display_crop",
                original_metadata=original_metadata
            )
        except Exception as e:
            classifier_error = True
            error_msg = str(e)
            full_res = None
            crop_res = None

        # 6. Fail-closed handling on classifier outage
        if classifier_error:
            self.audit_logger.log_classifier_error(
                media_id=media_id,
                error_message=error_msg,
                fallback_action=policy_pack.image_gate.classifier_unavailable_action
            )
            # Route to review under fail-closed invariant
            self.blob_store.store(
                media_id=media_id,
                image_bytes=preprocessed_bytes,
                ttl_hours=policy_pack.image_gate.review_sla_hours
            )
            return ImageSafetyResult(
                nudity_score=0.0,
                explicit_score=0.0,
                suggestive_score=0.0,
                model_name=self.classifier.model_name,
                model_version=self.classifier.model_version,
                decision="REVIEW",
                reasons=["classifier_error_fail_closed"],
                perceptual_hashes=hashes
            )

        assert full_res is not None and crop_res is not None

        # Determine which crop yielded higher risk
        # Risk priority: max(explicit_score) -> max(nudity_score) -> max(suggestive_score)
        full_risk = max(full_res.explicit_score, full_res.nudity_score, full_res.suggestive_score)
        crop_risk = max(crop_res.explicit_score, crop_res.nudity_score, crop_res.suggestive_score)

        if crop_risk > full_risk:
            selected_res = crop_res
            crop_used: Literal["full", "display_crop"] = "display_crop"
        else:
            selected_res = full_res
            crop_used = "full"

        # 7. Pluggable OCR Explicit Text Check (stub)
        ocr_explicit = simulate_ocr_explicit or (
            "EXPLICIT" in original_metadata.get("ocr_simulated_text", "")
        )

        # 8. Evaluate policy pack thresholds and actions
        decision, reasons, tags = self._evaluate_policy(
            selected_res=selected_res,
            crop_used=crop_used,
            known_bad=known_bad,
            ocr_explicit=ocr_explicit,
            policy_pack=policy_pack
        )

        # 9. Handle storage and memory lifecycle
        if decision == "BLOCK":
            # Mandatory Invariant: zero byte persistence.
            # Hashes already computed in step 2. Image bytes discarded immediately.
            pass
        elif decision == "REVIEW":
            # Store in encrypted ReviewBlobStore with server-side blur
            self.blob_store.store(
                media_id=media_id,
                image_bytes=preprocessed_bytes,
                ttl_hours=policy_pack.image_gate.review_sla_hours
            )
        else:
            # ALLOW or ALLOW_TAGGED
            if policy_pack.image_gate.cache_allowed_media:
                # Optionally cached if enabled
                pass

        # 10. Audit log entry
        thresholds_in_effect = {
            "nudity_block": policy_pack.image_gate.nudity_block_threshold,
            "nudity_review": policy_pack.image_gate.nudity_review_threshold,
            "suggestive_tag": policy_pack.image_gate.suggestive_tag_threshold,
            "suggestive_action": policy_pack.image_gate.suggestive_action,
        }
        self.audit_logger.log_gate_decision(
            actor_id=actor_id,
            media_id=media_id,
            decision=decision,
            model_name=selected_res.model_name,
            model_version=selected_res.model_version,
            policy_pack=policy_pack.name,
            thresholds=thresholds_in_effect,
            reasons=reasons,
            crop_used=crop_used,
            scores={
                "nudity": selected_res.nudity_score,
                "explicit": selected_res.explicit_score,
                "suggestive": selected_res.suggestive_score,
            }
        )

        return ImageSafetyResult(
            nudity_score=selected_res.nudity_score,
            explicit_score=selected_res.explicit_score,
            suggestive_score=selected_res.suggestive_score,
            ocr_explicit_text=ocr_explicit,
            known_bad_hash_match=known_bad,
            crop_used=crop_used,
            backend_scores=selected_res.backend_scores,
            model_name=selected_res.model_name,
            model_version=selected_res.model_version,
            decision=decision,
            reasons=reasons,
            perceptual_hashes=hashes,
            applied_tags=tags
        )

    def _validate_and_preprocess(
        self,
        image_bytes: bytes
    ) -> tuple[dict[str, Any], bytes, Image.Image]:
        """Validate format, check pixel cap, extract metadata, apply EXIF orientation, strip EXIF."""
        # Check empty
        if not image_bytes:
            raise ValueError("Uploaded image payload is empty.")

        # Inspect format and pixel dimensions
        stream = io.BytesIO(image_bytes)
        try:
            with Image.open(stream) as probe_img:
                fmt = (probe_img.format or "").upper()
                if fmt not in ALLOWED_FORMATS:
                    raise UnsupportedFormatError(
                        f"Unsupported format '{fmt}'. Allowed formats are PNG, JPEG, WEBP. SVG is strictly prohibited."
                    )

                w, h = probe_img.size
                if (w * h) > PIXEL_CAP:
                    raise DecompressionBombError(
                        f"Image exceeds pixel cap ({w*h} > {PIXEL_CAP} pixels)."
                    )

                # Extract pre-strip metadata
                original_metadata: dict[str, Any] = {}
                if hasattr(probe_img, "text") and isinstance(probe_img.text, dict):
                    original_metadata.update(probe_img.text)

                # Apply EXIF orientation before stripping EXIF (Amendment 10)
                transposed = ImageOps.exif_transpose(probe_img)
                rgb_img = transposed.convert("RGB")
        except (UnsupportedFormatError, DecompressionBombError):
            raise
        except Exception as e:
            # Unidentified image or invalid header -> unsupported format
            if "cannot identify image" in str(e).lower():
                raise UnsupportedFormatError(f"Unsupported or invalid image format: {e}") from e
            raise ValueError(f"Failed to decode image: {e}") from e

        # Re-encode in-memory without EXIF/metadata
        clean_stream = io.BytesIO()
        rgb_img.save(clean_stream, format="PNG")
        clean_bytes = clean_stream.getvalue()

        return original_metadata, clean_bytes, rgb_img

    def _compute_hashes(self, img: Image.Image) -> dict[str, str]:
        """Compute perceptual hashes (pHash, dHash, wHash) and indexed mirror pHash."""
        p = str(imagehash.phash(img))
        d = str(imagehash.dhash(img))
        w = str(imagehash.whash(img))
        # Compute mirror hash for horizontal flip indexing (Amendment 6)
        mirrored = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        m_p = str(imagehash.phash(mirrored))
        return {
            "phash": p,
            "dhash": d,
            "whash": w,
            "mirror_phash": m_p
        }

    def _extract_avatar_crop(self, img: Image.Image, crop_size: int = 128) -> bytes:
        """Extract circular avatar thumbnail crop."""
        w, h = img.size
        # Center square bounding box
        dim = min(w, h)
        left = (w - dim) // 2
        top = (h - dim) // 2
        square = img.crop((left, top, left + dim, top + dim))
        resized = square.resize((crop_size, crop_size), Image.Resampling.LANCZOS)

        # Inscribe in circular mask
        mask = Image.new("L", (crop_size, crop_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, crop_size, crop_size), fill=255)

        circular = Image.new("RGB", (crop_size, crop_size), (240, 240, 240))
        circular.paste(resized, (0, 0), mask=mask)

        out = io.BytesIO()
        circular.save(out, format="PNG")
        return out.getvalue()

    def _evaluate_policy(
        self,
        selected_res: Any,
        crop_used: str,
        known_bad: bool,
        ocr_explicit: bool,
        policy_pack: PolicyPack
    ) -> tuple[Literal["ALLOW", "ALLOW_TAGGED", "REVIEW", "BLOCK"], list[str], list[str]]:
        """Evaluate raw scores against active policy pack."""
        reasons: list[str] = []
        tags: list[str] = []

        # 1. Known-bad hash check
        if known_bad:
            reasons.append("known_bad_hash_match")
            return "BLOCK", reasons, tags

        # 2. OCR Explicit text
        if ocr_explicit:
            reasons.append("ocr_explicit_text_detected")
            if policy_pack.image_gate.ocr_explicit_text_action == "BLOCK":
                return "BLOCK", reasons, tags
            else:
                return "REVIEW", reasons, tags

        cfg = policy_pack.image_gate

        # 3. Explicit / Nudity thresholds
        if selected_res.explicit_score >= 0.80 or selected_res.nudity_score >= cfg.nudity_block_threshold:
            reasons.append("exceeds_nudity_block_threshold")
            if crop_used == "display_crop":
                reasons.append("crop_score_triggered_block")
            return "BLOCK", reasons, tags

        if selected_res.nudity_score >= cfg.nudity_review_threshold:
            reasons.append("nudity_score_in_review_band")
            return "REVIEW", reasons, tags

        # 4. Suggestive Presentation threshold
        if selected_res.suggestive_score >= cfg.suggestive_tag_threshold:
            reasons.append("elevated_suggestive_presentation")
            tags.append("suggestive_presentation")

            action = cfg.suggestive_action
            if action == "REVIEW":
                return "REVIEW", reasons, tags
            elif action == "BLOCK":
                return "BLOCK", reasons, tags
            elif action == "ALLOW_TAGGED":
                return "ALLOW_TAGGED", reasons, tags
            else:
                return "ALLOW", reasons, []

        return "ALLOW", reasons, tags
