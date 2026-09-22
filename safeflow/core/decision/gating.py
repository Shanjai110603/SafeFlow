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
    """Enforces multi-signal confirmation and non-overridable gating rules.

    Invariants:
    1. Single-Signal Protection: Isolated suggestive presentation tags or AI flags alone CANNOT exceed LOW risk.
    2. High-Risk Multi-Family Requirement: HIGH risk strictly requires >= 3 distinct activated signal families.
    3. Critical-Risk Multi-Family Requirement: CRITICAL risk strictly requires >= 4 distinct activated signal families.
    4. Anti-Circumvention: Downward adjustments record explicit audit trail reasons for explainability.
    """

    # Activation threshold for a signal to count as an actively triggered family
    FAMILY_TRIGGER_THRESHOLD = 0.50

    @classmethod
    def extract_triggered_families(
        cls,
        signals: Sequence[Signal],
        threshold: float = FAMILY_TRIGGER_THRESHOLD,
    ) -> set[str]:
        """Extract the set of distinct signal family names where at least one signal exceeds the threshold.

        Args:
            signals: Sequence of multi-modal signals.
            threshold: Minimum signal value to consider a family activated (default 0.50).

        Returns:
            Set of active family names (e.g. {'BEHAVIOR', 'DESTINATION', 'TARGETING'}).
        """
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
        """Apply mathematical gating constraints to raw risk classification.

        Args:
            raw_level: Initial un-gated RiskLevel from scoring model.
            raw_score: 0-100 numerical risk score.
            signals: Sequence of input signals evaluated.

        Returns:
            Tuple of (gated_risk_level, list_of_gating_audit_reasons).
        """
        gating_reasons: list[str] = []
        triggered_families = cls.extract_triggered_families(signals)
        num_families = len(triggered_families)

        # -------------------------------------------------------------------------
        # Invariant 1: Single-Signal Protection for Suggestive / AI Flags
        # -------------------------------------------------------------------------
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
        
        non_image_families = {f for f in triggered_families if f != "IMAGE_LINK"}
        # If suggestive presentation or AI flag is active without corroborating non-image families:
        if (has_suggestive or has_ai_flag) and len(non_image_families) == 0:
            if raw_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
                gating_reasons.append(
                    "Downgraded to LOW: Single-signal protection (suggestive presentation or AI likelihood alone cannot exceed LOW)"
                )
                return RiskLevel.LOW, gating_reasons

        # -------------------------------------------------------------------------
        # Invariant 2: CRITICAL Risk requires >= 4 distinct activated signal families
        # -------------------------------------------------------------------------
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

        # -------------------------------------------------------------------------
        # Invariant 3: HIGH Risk requires >= 3 distinct activated signal families
        # -------------------------------------------------------------------------
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

        # -------------------------------------------------------------------------
        # Invariant 4: MEDIUM Risk requires at least 2 families or high severity score
        # -------------------------------------------------------------------------
        if raw_level == RiskLevel.MEDIUM:
            if num_families < 2 and raw_score < 65.0:
                raw_level = RiskLevel.LOW
                gating_reasons.append(
                    f"Downgraded from MEDIUM to LOW: Isolated single family with sub-critical severity (got {num_families})"
                )

        return raw_level, gating_reasons
