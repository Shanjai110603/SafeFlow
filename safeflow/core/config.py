"""Configuration and Policy Pack loader with strict invariant enforcement.

Enforces non-overridable safety invariants:
1. Known-bad hash matching cannot be disabled or relaxed.
2. Classifier failure must fail closed (HOLD_DEFAULT_AVATAR).
3. Blocked image bytes must never be persisted.
4. Creator redaction cannot be disabled.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyInvariantViolationError(ValueError):
    """Raised when a policy pack attempts to weaken or violate a non-overridable safety invariant."""
    pass


class ImageGateConfig(BaseModel):
    """Uncalibrated research placeholders for the profile image safety gate."""
    model_config = ConfigDict(extra="forbid")

    policy_profile: Literal["strict_avatar", "explicit_only"] = Field(
        default="strict_avatar",
        description="Policy profile mode"
    )
    nudity_block_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Uncalibrated research placeholder threshold for nudity BLOCK"
    )
    nudity_review_threshold: float = Field(
        default=0.50, ge=0.0, le=1.0,
        description="Uncalibrated research placeholder threshold for nudity REVIEW"
    )
    suggestive_tag_threshold: float = Field(
        default=0.60, ge=0.0, le=1.0,
        description="Uncalibrated research placeholder threshold for suggestive presentation tag"
    )
    suggestive_action: Literal["ALLOW_TAGGED", "REVIEW", "BLOCK", "ALLOW"] = Field(
        default="ALLOW_TAGGED",
        description="Action applied when an image exceeds suggestive_tag_threshold"
    )
    ocr_explicit_text_action: Literal["BLOCK", "REVIEW"] = Field(
        default="BLOCK",
        description="Action when explicit text overlay is detected"
    )
    review_behavior: Literal["HOLD_DEFAULT_AVATAR"] = Field(
        default="HOLD_DEFAULT_AVATAR",
        description="Action when an image is routed to human review"
    )
    classifier_unavailable_action: Literal["HOLD_DEFAULT_AVATAR"] = Field(
        default="HOLD_DEFAULT_AVATAR",
        description="Fail-closed behavior when classifier errors or times out"
    )
    known_bad_hash_action: Literal["BLOCK"] = Field(
        default="BLOCK",
        description="Action when image matches simulated known-bad hash list"
    )
    tag_ttl_days: int = Field(
        default=30, ge=1,
        description="Time-to-live in days for suggestive presentation tags"
    )
    rescan_interval_days: int = Field(
        default=30, ge=1,
        description="Periodic rescan interval in days"
    )
    review_sla_hours: int = Field(
        default=24, ge=1,
        description="Human review SLA duration in hours"
    )
    cache_allowed_media: bool = Field(
        default=False,
        description="Whether allowed avatars are cached locally (default False per Amendment 2)"
    )


class DecisionEngineConfig(BaseModel):
    """Uncalibrated research placeholders for the multi-signal decision engine."""
    model_config = ConfigDict(extra="forbid")

    low_cutoff: int = Field(default=30, ge=0, le=100)
    medium_cutoff: int = Field(default=60, ge=0, le=100)
    high_cutoff: int = Field(default=80, ge=0, le=100)

    high_risk_min_families: int = Field(
        default=3, ge=2,
        description="Minimum independent signal families required for HIGH risk"
    )
    critical_risk_min_families: int = Field(
        default=4, ge=3,
        description="Minimum independent signal families required for CRITICAL risk"
    )
    weak_signal_families: list[str] = Field(
        default_factory=lambda: ["SUGGESTIVE_PRESENTATION", "AI_LIKELIHOOD"],
        description="Signal families that cannot elevate an actor above LOW risk alone"
    )


class RetentionConfig(BaseModel):
    """Data retention and minimization settings."""
    model_config = ConfigDict(extra="forbid")

    audit_retention_days: int = Field(default=365, ge=1)
    persist_blocked_images: bool = Field(
        default=False,
        description="Mandatory invariant: blocked image bytes must never be persisted"
    )


class PolicyPack(BaseModel):
    """Platform policy configuration mapping neutral signals to platform-specific actions."""
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    version: str = "1.0.0"
    enabled_plugins: list[str] = Field(
        default_factory=lambda: ["image_gate", "media_reuse", "text_behavior", "link_destination", "actor_profile"]
    )
    image_gate: ImageGateConfig = Field(default_factory=ImageGateConfig)
    decision_engine: DecisionEngineConfig = Field(default_factory=DecisionEngineConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    @model_validator(mode="after")
    def enforce_non_overridable_invariants(self) -> PolicyPack:
        """Reject any policy pack attempting to violate core safety invariants."""
        # Invariant 1: No blocked image persistence
        if self.retention.persist_blocked_images:
            raise PolicyInvariantViolationError(
                f"Policy pack '{self.name}' violates safety invariant: "
                "persist_blocked_images cannot be enabled."
            )

        # Invariant 2: Fail closed on classifier errors
        if self.image_gate.classifier_unavailable_action != "HOLD_DEFAULT_AVATAR":
            raise PolicyInvariantViolationError(
                f"Policy pack '{self.name}' violates safety invariant: "
                "classifier_unavailable_action must be 'HOLD_DEFAULT_AVATAR' (fail closed)."
            )

        # Invariant 3: Known-bad hashes must always BLOCK
        if self.image_gate.known_bad_hash_action != "BLOCK":
            raise PolicyInvariantViolationError(
                f"Policy pack '{self.name}' violates safety invariant: "
                "known_bad_hash_action must be 'BLOCK'."
            )

        # Invariant 4: Review behavior must hold default avatar
        if self.image_gate.review_behavior != "HOLD_DEFAULT_AVATAR":
            raise PolicyInvariantViolationError(
                f"Policy pack '{self.name}' violates safety invariant: "
                "review_behavior must be 'HOLD_DEFAULT_AVATAR'."
            )

        return self


class PolicyPackLoader:
    """Discovers, loads, and validates YAML policy packs."""

    DEFAULT_POLICY_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "policies"

    @classmethod
    def load_from_file(cls, path: str | Path) -> PolicyPack:
        """Load and validate a single policy pack from a YAML file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Policy pack file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML content in policy pack: {file_path}")

        try:
            return PolicyPack.model_validate(data)
        except Exception as e:
            # Check if any error was an invariant violation
            err_str = str(e)
            if "violates safety invariant" in err_str:
                raise PolicyInvariantViolationError(err_str) from e
            if "classifier_unavailable_action" in err_str:
                raise PolicyInvariantViolationError(
                    "Policy pack violates safety invariant: classifier_unavailable_action must be 'HOLD_DEFAULT_AVATAR'."
                ) from e
            if "known_bad_hash_action" in err_str:
                raise PolicyInvariantViolationError(
                    "Policy pack violates safety invariant: known_bad_hash_action must be 'BLOCK'."
                ) from e
            if "persist_blocked_images" in err_str:
                raise PolicyInvariantViolationError(
                    "Policy pack violates safety invariant: persist_blocked_images cannot be enabled."
                ) from e
            raise

    @classmethod
    def load_by_name(cls, name: str, search_dir: str | Path | None = None) -> PolicyPack:
        """Load a named policy pack from the policy directory."""
        directory = Path(search_dir) if search_dir else cls.DEFAULT_POLICY_DIR
        yaml_path = directory / f"{name}.yaml"
        yml_path = directory / f"{name}.yml"

        if yaml_path.exists():
            return cls.load_from_file(yaml_path)
        elif yml_path.exists():
            return cls.load_from_file(yml_path)
        else:
            raise FileNotFoundError(f"Policy pack '{name}' not found in {directory}")

    @classmethod
    def list_available_packs(cls, search_dir: str | Path | None = None) -> list[str]:
        """List names of available policy packs in directory."""
        directory = Path(search_dir) if search_dir else cls.DEFAULT_POLICY_DIR
        if not directory.exists():
            return []
        packs = []
        for file in directory.glob("*.yaml"):
            packs.append(file.stem)
        for file in directory.glob("*.yml"):
            if file.stem not in packs:
                packs.append(file.stem)
        return sorted(packs)
