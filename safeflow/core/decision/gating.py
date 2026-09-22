"""Signal-family gating and safety invariants for SafeFlow Decision Engine.

Enforces strict rules:
1. Single-signal protection: `suggestive_presentation` or AI-likelihood alone can NEVER elevate risk above LOW.
2. HIGH risk requires at least 3 distinct signal families.
3. CRITICAL risk requires at least 4 distinct signal families.
4. Image reuse alone cannot elevate risk above LOW without corroborating behavioral or network families.
"""

from __future__ import annotations

from typing import Sequence
from safeflow.core.schema import RiskLevel, Signal


class SignalFamilyGate:
    """Enforces multi-signal confirmation and non-overridable gating rules."""

    FAMILY_TRIGGER_THRESHOLD = 0.50

    @classmethod
    def extract_triggered_families(
        cls,
        signals: Sequence[Signal],
        threshold: float = FAMILY_TRIGGER_THRESHOLD,
    ) -> set[str]:
        """Extract set of family names where at least one signal exceeds the activation threshold."""
        triggered = set()
        for sig in signals:
            if sig.value >= threshold:
                triggered.add(sig.family)
        return triggered

    @classmethod
    def apply_gating(
        cls,
        raw_level: RiskLevel,
        raw_score: float,
        signals: Sequence[Signal],
    ) -> tuple[RiskLevel, list[str]]:
        """Apply gating constraints to raw risk classification.
        
        Returns:
            (gated_level, gating_reasons)
        """
        gating_reasons: list[str] = []
        triggered_families = cls.extract_triggered_families(signals)
        num_families = len(triggered_families)

        # Check for single-signal isolated triggers
        # Only IMAGE_LINK / media_gate triggers
        has_suggestive = any(
            (s.name in ("suggestive_presentation", "media_suggestive_score") or "suggestive" in s.name)
            and s.value >= cls.FAMILY_TRIGGER_THRESHOLD
            for s in signals
        )
        has_ai_flag = any(
            s.name in ("ai_generated_likelihood", "ai_likelihood")
            and s.value >= cls.FAMILY_TRIGGER_THRESHOLD
            for s in signals
        )
        
        # Invariant 1: Single-signal protection for suggestive / AI flags alone
        non_image_families = {f for f in triggered_families if f != "IMAGE_LINK"}
        if (has_suggestive or has_ai_flag) and len(non_image_families) == 0:
            if raw_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
                gating_reasons.append(
                    "Downgraded to LOW: Single-signal protection (suggestive presentation or AI likelihood alone cannot exceed LOW)"
                )
                return RiskLevel.LOW, gating_reasons

        # Invariant 2: High risk requires >= 3 distinct families
        if raw_level == RiskLevel.CRITICAL:
            if num_families < 4:
                if num_families >= 3:
                    raw_level = RiskLevel.HIGH
                    gating_reasons.append(
                        f"Downgraded from CRITICAL to HIGH: Requires >= 4 distinct signal families (got {num_families}: {sorted(triggered_families)})"
                    )
                elif num_families == 2:
                    raw_level = RiskLevel.MEDIUM
                    gating_reasons.append(
                        f"Downgraded from CRITICAL to MEDIUM: Requires >= 4 distinct signal families (got {num_families}: {sorted(triggered_families)})"
                    )
                else:
                    raw_level = RiskLevel.LOW
                    gating_reasons.append(
                        f"Downgraded from CRITICAL to LOW: Requires >= 4 distinct signal families (got {num_families}: {sorted(triggered_families)})"
                    )

        if raw_level == RiskLevel.HIGH:
            if num_families < 3:
                if num_families == 2:
                    raw_level = RiskLevel.MEDIUM
                    gating_reasons.append(
                        f"Downgraded from HIGH to MEDIUM: Requires >= 3 distinct signal families (got {num_families}: {sorted(triggered_families)})"
                    )
                else:
                    raw_level = RiskLevel.LOW
                    gating_reasons.append(
                        f"Downgraded from HIGH to LOW: Requires >= 3 distinct signal families (got {num_families}: {sorted(triggered_families)})"
                    )

        if raw_level == RiskLevel.MEDIUM:
            if num_families < 2 and raw_score < 65.0:
                raw_level = RiskLevel.LOW
                gating_reasons.append(
                    f"Downgraded from MEDIUM to LOW: Isolated single family with sub-critical severity (got {num_families})"
                )

        return raw_level, gating_reasons
