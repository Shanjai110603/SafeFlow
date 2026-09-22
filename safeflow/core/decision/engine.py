"""Explainable Decision Engine for SafeFlow.

Orchestrates heuristic and calibrated scoring, signal-family gating,
evidence explanation generation, and policy pack recommendation mapping.
"""

from __future__ import annotations

from typing import Literal, Sequence
from safeflow.core.schema import Decision, RiskLevel, Signal
from safeflow.core.config import PolicyPack, PolicyPackLoader
from safeflow.core.decision.heuristic import HeuristicScorer
from safeflow.core.decision.calibrated import CalibratedScorer
from safeflow.core.decision.gating import SignalFamilyGate
from safeflow.core.decision.explainer import DecisionExplainer


class DecisionEngine:
    """Multi-tiered explainable decision engine."""

    def __init__(
        self,
        policy_pack: PolicyPack | None = None,
        heuristic_scorer: HeuristicScorer | None = None,
        calibrated_scorer: CalibratedScorer | None = None,
    ) -> None:
        self.policy_pack = policy_pack or PolicyPackLoader.load_default()
        self.heuristic_scorer = heuristic_scorer or HeuristicScorer()
        self.calibrated_scorer = calibrated_scorer or CalibratedScorer()

    def train_calibrated(
        self,
        X,
        y,
        groups=None,
    ) -> "DecisionEngine":
        """Train the calibrated classifier on development set data."""
        self.calibrated_scorer.fit(X, y, groups=groups)
        return self

    def _determine_policy_action(self, level: RiskLevel) -> str:
        """Map evaluated risk level to platform-specific recommended policy action."""
        pack_name = getattr(self.policy_pack, "name", "default")

        if pack_name == "youth_oriented_service":
            if level == RiskLevel.CRITICAL:
                return "Immediate account suspension, domain network block, and session invalidation"
            elif level == RiskLevel.HIGH:
                return "Restrict discovery visibility, hold bio links, and route to tier-1 moderation queue"
            elif level == RiskLevel.MEDIUM:
                return "Apply link hold verification queue and rate-limit comment velocity"
            else:
                return "Allow standard activity; low youth safety risk"

        elif pack_name == "adult_permitted_platform":
            if level == RiskLevel.CRITICAL:
                return "Suspend account for malicious off-platform redirection or spam farm abuse"
            elif level == RiskLevel.HIGH:
                return "Route to compliance queue for link destination and age verification check"
            elif level == RiskLevel.MEDIUM:
                return "Flag for destination URL domain reputation check"
            else:
                return "Allow standard activity; compliant presentation"

        else:  # general_video_platform or default
            if level == RiskLevel.CRITICAL:
                return "Suspend actor account, invalidate active sessions, and block associated destination URLs"
            elif level == RiskLevel.HIGH:
                return "Route actor to high-priority moderation queue for manual review"
            elif level == RiskLevel.MEDIUM:
                return "Flag actor for automated rate limiting and link hold verification"
            else:
                return "Allow standard activity; no policy action required"

    def evaluate_actor(
        self,
        actor_id: str,
        signals: Sequence[Signal],
        mode: Literal["heuristic", "calibrated"] = "heuristic",
    ) -> Decision:
        """Evaluate actor signals and produce an explainable canonical Decision."""
        if mode == "calibrated" and self.calibrated_scorer.is_fitted:
            score, level, gating_reasons = self.calibrated_scorer.score_actor(signals)
        else:
            score, level, gating_reasons = self.heuristic_scorer.score_actor(signals)

        triggered_families = SignalFamilyGate.extract_triggered_families(signals)
        evidence, counter_evidence = DecisionExplainer.generate_explanation(signals, gating_reasons)
        action = self._determine_policy_action(level)

        return Decision(
            subject=actor_id,
            level=level,
            score=round(score, 2),
            families_triggered=sorted(list(triggered_families)),
            evidence=evidence,
            counter_evidence=counter_evidence,
            recommended_action=action,
            visibility="analyst",
        )
