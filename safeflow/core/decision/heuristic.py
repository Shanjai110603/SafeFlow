"""Heuristic baseline scorer for SafeFlow Decision Engine.

Transparent, deterministic, rule-weighted baseline scoring across 5 canonical signal families.
"""

from __future__ import annotations

from typing import Sequence
from safeflow.core.schema import RiskLevel, Signal
from safeflow.core.decision.gating import SignalFamilyGate


class HeuristicScorer:
    """Computes transparent weighted baseline risk scores and levels."""

    DEFAULT_WEIGHTS: dict[str, float] = {
        "IMAGE_LINK": 0.20,
        "BEHAVIOR": 0.20,
        "TARGETING": 0.20,
        "DESTINATION": 0.25,
        "PROFILE_CHANGE": 0.15,
    }

    def __init__(self, family_weights: dict[str, float] | None = None) -> None:
        self.family_weights = family_weights or dict(self.DEFAULT_WEIGHTS)
        # Normalize weights so sum is 1.0
        total = sum(self.family_weights.values())
        if total > 0:
            self.family_weights = {k: v / total for k, v in self.family_weights.items()}

    def score_actor(
        self,
        signals: Sequence[Signal],
    ) -> tuple[float, RiskLevel, list[str]]:
        """Evaluate signals for a single actor.
        
        Returns:
            (composite_score_0_100, final_risk_level, gating_reasons)
        """
        if not signals:
            return 0.0, RiskLevel.LOW, ["No signals present"]

        # Group max value per family to avoid double-counting within a single family
        family_max_values: dict[str, float] = {}
        for sig in signals:
            current = family_max_values.get(sig.family, 0.0)
            if sig.value > current:
                family_max_values[sig.family] = sig.value

        # Calculate weighted sum
        weighted_sum = 0.0
        for family, val in family_max_values.items():
            w = self.family_weights.get(family, 0.10)
            weighted_sum += val * w

        score = max(0.0, min(100.0, weighted_sum * 100.0))

        # Raw risk level assignment based on standard thresholds
        if score >= 65.0:
            raw_level = RiskLevel.CRITICAL
        elif score >= 42.0:
            raw_level = RiskLevel.HIGH
        elif score >= 20.0:
            raw_level = RiskLevel.MEDIUM
        else:
            raw_level = RiskLevel.LOW

        # Apply multi-signal family gating and safety invariants
        final_level, gating_reasons = SignalFamilyGate.apply_gating(
            raw_level=raw_level,
            raw_score=score,
            signals=signals,
        )

        return score, final_level, gating_reasons
