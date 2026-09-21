"""ImageGatePlugin wrapping ImageGatePipeline as a canonical SignalPlugin."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel
from safeflow.core.config import ImageGateConfig, PolicyPack
from safeflow.core.registry import global_plugin_registry
from safeflow.core.schema import Media, Signal
from safeflow.plugins.base import BaseSignalPlugin
from safeflow.plugins.image_gate.classifier import ImageSafetyClassifier
from safeflow.plugins.image_gate.pipeline import ImageGatePipeline, ImageSafetyResult


class ImageGatePlugin(BaseSignalPlugin):
    """Profile Image Safety Gate SignalPlugin."""

    name: str = "image_gate"
    family: str = "IMAGE_LINK"
    version: str = "1.0.0"
    requires: list[str] = ["media"]

    def __init__(
        self,
        classifier: ImageSafetyClassifier | None = None,
        pipeline: ImageGatePipeline | None = None
    ) -> None:
        self.pipeline = pipeline or ImageGatePipeline(classifier=classifier)

    def get_config_schema(self) -> type[BaseModel] | None:
        return ImageGateConfig

    def assess_image_bytes(
        self,
        image_bytes: bytes,
        policy_pack: PolicyPack,
        actor_id: str = "anon",
        media_id: str = "media_1"
    ) -> ImageSafetyResult:
        """Direct entry point to assess raw image bytes."""
        return self.pipeline.process(
            image_bytes=image_bytes,
            policy_pack=policy_pack,
            actor_id=actor_id,
            media_id=media_id
        )

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        """Execute image gate assessment over a batch of canonical Media entities."""
        signals: list[Signal] = []
        ctx = context or {}
        policy_pack = ctx.get("policy_pack")
        if not policy_pack or not isinstance(policy_pack, PolicyPack):
            from safeflow.core.config import PolicyPackLoader
            policy_pack = PolicyPackLoader.load_by_name("default_research")

        now = datetime.now(timezone.utc)
        media_fetcher = ctx.get("media_fetcher")

        for item in batch:
            media_id = getattr(item, "media_id", None) or (item.get("media_id") if isinstance(item, dict) else None)
            actor_id = getattr(item, "actor_id", "anon") or (item.get("actor_id", "anon") if isinstance(item, dict) else "anon")
            image_bytes = ctx.get(f"bytes_{media_id}")

            if not image_bytes and media_fetcher:
                image_bytes = media_fetcher.fetch_media(media_id)

            if not image_bytes:
                continue

            result = self.pipeline.process(
                image_bytes=image_bytes,
                policy_pack=policy_pack,
                actor_id=actor_id,
                media_id=media_id
            )

            # Emit canonical signals based on objective findings
            if "suggestive_presentation" in result.applied_tags:
                signals.append(
                    Signal(
                        subject_type="media",
                        subject_id=str(media_id),
                        family=self.family,
                        name="suggestive_presentation_flag",
                        value=result.suggestive_score,
                        confidence=1.0,
                        evidence_refs=[str(media_id)],
                        producer=self.name,
                        producer_version=self.version,
                        ts=now
                    )
                )

            # Signal for perceptual hash presence
            if result.perceptual_hashes:
                signals.append(
                    Signal(
                        subject_type="media",
                        subject_id=str(media_id),
                        family=self.family,
                        name="perceptual_phash_computed",
                        value=1.0,
                        confidence=1.0,
                        evidence_refs=[str(media_id)],
                        producer=self.name,
                        producer_version=self.version,
                        ts=now
                    )
                )

        return signals


# Register instance with global registry
global_plugin_registry.register(ImageGatePlugin())
