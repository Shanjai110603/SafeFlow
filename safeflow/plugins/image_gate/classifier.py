"""Image Safety Classifiers and Protocols for SafeFlow.

Includes:
- ImageSafetyClassifier protocol
- MockClassifier: reads pre-strip PNG metadata and detects non-depictive pixel markers
- EnsembleClassifier: multi-backend combination logic
- LocalModelClassifier stub (OpenNSFW2 / NudeNet / Falconsai)
- ManagedAPIClassifier stub (with external data transfer warnings)
"""

from __future__ import annotations

import io
import warnings
from typing import Any, Literal, Protocol, runtime_checkable
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from safeflow.utils.procedural_avatar import (
    GroundTruthLabel,
    ProceduralAvatarGenerator,
)


class RawClassificationResult(BaseModel):
    """Raw predictions emitted by an ImageSafetyClassifier backend."""
    model_config = ConfigDict(extra="forbid")

    nudity_score: float = Field(..., ge=0.0, le=1.0)
    explicit_score: float = Field(..., ge=0.0, le=1.0)
    suggestive_score: float = Field(..., ge=0.0, le=1.0)
    model_name: str
    model_version: str
    backend_scores: dict[str, float] = Field(default_factory=dict)
    raw_label: str = "NEUTRAL"


@runtime_checkable
class ImageSafetyClassifier(Protocol):
    """Protocol for image moderation model backends."""

    @property
    def model_name(self) -> str:
        ...

    @property
    def model_version(self) -> str:
        ...

    def classify(
        self,
        image_bytes: bytes,
        crop_kind: Literal["full", "display_crop"] = "full",
        original_metadata: dict[str, Any] | None = None
    ) -> RawClassificationResult:
        """Evaluate image bytes and return raw classification predictions."""
        ...


class MockClassifier:
    """Deterministic, uncalibrated research placeholder classifier for tests and demonstrations.

    Reads ground truth from:
    1. Pre-strip original metadata (safeflow_ground_truth / safeflow_crop_ground_truth)
    2. Non-depictive geometric pixel markers at defined regions (perimeter vs crop)
    """

    def __init__(
        self,
        model_name: str = "mock_classifier",
        model_version: str = "1.0.0",
        simulate_error: bool = False
    ) -> None:
        self._name = model_name
        self._version = model_version
        self.simulate_error = simulate_error

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def model_version(self) -> str:
        return self._version

    def classify(
        self,
        image_bytes: bytes,
        crop_kind: Literal["full", "display_crop"] = "full",
        original_metadata: dict[str, Any] | None = None
    ) -> RawClassificationResult:
        if self.simulate_error:
            raise RuntimeError("MockClassifier: Simulated classifier outage / timeout.")

        label: GroundTruthLabel = "NEUTRAL"

        # 1. Inspect original metadata if available
        if original_metadata:
            if crop_kind == "display_crop" and "safeflow_crop_ground_truth" in original_metadata:
                label = original_metadata["safeflow_crop_ground_truth"]
            elif "safeflow_ground_truth" in original_metadata:
                label = original_metadata["safeflow_ground_truth"]

        # 2. Inspect embedded PNG text chunks directly if metadata not supplied
        if label == "NEUTRAL":
            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    if hasattr(img, "text") and isinstance(img.text, dict):
                        if crop_kind == "display_crop" and "safeflow_crop_ground_truth" in img.text:
                            label = img.text["safeflow_crop_ground_truth"]  # type: ignore[assignment]
                        elif "safeflow_ground_truth" in img.text:
                            label = img.text["safeflow_ground_truth"]  # type: ignore[assignment]
            except Exception:
                pass

        # 3. Amendment 1: Inspect non-depictive geometric pixel markers
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                region: Literal["crop", "perimeter"] = "crop" if crop_kind == "display_crop" else "perimeter"
                detected_marker = ProceduralAvatarGenerator.detect_pixel_marker(img, region=region)
                if detected_marker:
                    label = detected_marker
        except Exception:
            pass

        # Generate deterministic uncalibrated research placeholder scores
        nudity = 0.02
        explicit = 0.01
        suggestive = 0.05

        if label == "EXPLICIT":
            explicit = 0.98
            nudity = 0.95
            suggestive = 0.20
        elif label == "NUDITY":
            explicit = 0.10
            nudity = 0.95
            suggestive = 0.40
        elif label == "SUGGESTIVE":
            explicit = 0.02
            nudity = 0.05
            suggestive = 0.75
        elif label == "AMBIGUOUS":
            explicit = 0.05
            nudity = 0.52   # Falls in review band [0.50, 0.85)
            suggestive = 0.55
        elif label == "NEUTRAL":
            explicit = 0.01
            nudity = 0.02
            suggestive = 0.05

        return RawClassificationResult(
            nudity_score=nudity,
            explicit_score=explicit,
            suggestive_score=suggestive,
            model_name=self._name,
            model_version=self._version,
            backend_scores={
                f"{self._name}_nudity": nudity,
                f"{self._name}_explicit": explicit,
                f"{self._name}_suggestive": suggestive,
            },
            raw_label=label
        )


class EnsembleClassifier:
    """Combines multiple classifier backends with configurable aggregation logic."""

    def __init__(
        self,
        classifiers: list[ImageSafetyClassifier],
        model_name: str = "ensemble_classifier",
        model_version: str = "1.0.0"
    ) -> None:
        if not classifiers:
            raise ValueError("EnsembleClassifier requires at least one sub-classifier.")
        self.classifiers = classifiers
        self._name = model_name
        self._version = model_version

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def model_version(self) -> str:
        return self._version

    def classify(
        self,
        image_bytes: bytes,
        crop_kind: Literal["full", "display_crop"] = "full",
        original_metadata: dict[str, Any] | None = None
    ) -> RawClassificationResult:
        all_backend_scores: dict[str, float] = {}
        max_nudity = 0.0
        max_explicit = 0.0
        max_suggestive = 0.0

        for clf in self.classifiers:
            res = clf.classify(image_bytes, crop_kind=crop_kind, original_metadata=original_metadata)
            for k, v in res.backend_scores.items():
                all_backend_scores[k] = v

            # Escalation rule: maximum risk score across calibrated backends
            max_nudity = max(max_nudity, res.nudity_score)
            max_explicit = max(max_explicit, res.explicit_score)
            max_suggestive = max(max_suggestive, res.suggestive_score)

        return RawClassificationResult(
            nudity_score=max_nudity,
            explicit_score=max_explicit,
            suggestive_score=max_suggestive,
            model_name=self._name,
            model_version=self._version,
            backend_scores=all_backend_scores,
            raw_label="ENSEMBLE"
        )


class LocalModelClassifier:
    """Interface stub for optional local ML models (OpenNSFW2, NudeNet, Falconsai)."""

    def __init__(self, backend_type: str = "opennsfw2", model_version: str = "uninstalled") -> None:
        self.backend_type = backend_type
        self._version = model_version
        self._available = False

    @property
    def model_name(self) -> str:
        return f"local_{self.backend_type}"

    @property
    def model_version(self) -> str:
        return self._version

    def classify(
        self,
        image_bytes: bytes,
        crop_kind: Literal["full", "display_crop"] = "full",
        original_metadata: dict[str, Any] | None = None
    ) -> RawClassificationResult:
        if not self._available:
            raise NotImplementedError(
                f"Local backend '{self.backend_type}' is not installed. "
                "Install via optional extras (e.g. pip install -e '.[local_models]')."
            )
        return RawClassificationResult(
            nudity_score=0.0,
            explicit_score=0.0,
            suggestive_score=0.0,
            model_name=self.model_name,
            model_version=self.model_version
        )


class ManagedAPIClassifier:
    """Interface stub for third-party commercial APIs (Sightengine, Hive, Cloud Vision).

    DISABLED BY DEFAULT to prevent accidental transmission of user images to third parties.
    """

    def __init__(self, provider: str = "generic_commercial") -> None:
        self.provider = provider
        self.enabled = False

    @property
    def model_name(self) -> str:
        return f"api_{self.provider}"

    @property
    def model_version(self) -> str:
        return "1.0.0"

    def classify(
        self,
        image_bytes: bytes,
        crop_kind: Literal["full", "display_crop"] = "full",
        original_metadata: dict[str, Any] | None = None
    ) -> RawClassificationResult:
        if not self.enabled:
            raise PermissionError(
                f"Managed API '{self.provider}' is disabled by default. "
                "WARNING: Enabling managed moderation APIs sends user image bytes to a third-party server, "
                "requiring data privacy compliance reviews (GDPR / India DPDP Act)."
            )
        return RawClassificationResult(
            nudity_score=0.0,
            explicit_score=0.0,
            suggestive_score=0.0,
            model_name=self.model_name,
            model_version=self.model_version
        )
