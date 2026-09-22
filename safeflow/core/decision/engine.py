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
    """Multi-tiered explainable decision engine.

    Combines:
    1. Weighted heuristic baseline scoring or group-calibrated logistic scoring.
    2. Non-overridable signal-family gating invariants (single-signal protection).
    3. Structured natural-language evidence and mitigating counter-evidence generation.
    4. Platform-tailored policy pack recommendation mapping.
    """

    def __init__(
        self,
        policy_pack: PolicyPack | None = None,
        heuristic_scorer: HeuristicScorer | None = None,
        calibrated_scorer: CalibratedScorer | None = None,
    ) -> None:
        """Initialize DecisionEngine with policy configurations and scoring backends.

        Args:
            policy_pack: Active platform policy pack defining thresholds and action mapping.
            heuristic_scorer: Rule-based transparent weighted scorer.
            calibrated_scorer: Group-aware logistic regression model with Platt scaling.
        """
        self.policy_pack = policy_pack or PolicyPackLoader.load_default()
        self.heuristic_scorer = heuristic_scorer or HeuristicScorer()
        self.calibrated_scorer = calibrated_scorer or CalibratedScorer()

    def train_calibrated(
        self,
        X,
        y,
        groups=None,
    ) -> "DecisionEngine":
        """Train the calibrated classifier on development set feature vectors.

        Args:
            X: Matrix of shape (n_samples, n_features).
            y: Binary target labels (0 for benign, 1 for attack).
            groups: Optional cluster group IDs for GroupKFold cross-validation.
        """
        self.calibrated_scorer.fit(X, y, groups=groups)
        return self

    def _determine_policy_action(self, level: RiskLevel) -> str:
        """Map evaluated risk level to platform-specific recommended policy action.

        Args:
            level: Final evaluated RiskLevel (LOW, MEDIUM, HIGH, CRITICAL).

        Returns:
            Human-readable recommended remediation action for platform moderation queues.
        """
        pack_name = getattr(self.policy_pack, "name", "default")

        # Tailored policy actions based on platform safety context
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
        """Evaluate actor signals and produce an explainable canonical Decision.

        Pipeline Execution:
        1. Compute raw risk score and enforce multi-family gating invariants.
        2. Extract distinct triggered signal families.
        3. Synthesize human-readable evidence and mitigating counter-evidence.
        4. Map risk level to platform-specific remediation action.

        Args:
            actor_id: Unique subject identifier.
            signals: Sequence of multi-modal signals extracted for this actor.
            mode: 'heuristic' for deterministic weighted scoring, or 'calibrated' for statistical model.

        Returns:
            Canonical Decision object with risk level, score, evidence, and recommended actions.
        """
        # Step 1: Compute score and apply mathematical gating invariants
        if mode == "calibrated" and self.calibrated_scorer.is_fitted:
            score, level, gating_reasons = self.calibrated_scorer.score_actor(signals)
        else:
            score, level, gating_reasons = self.heuristic_scorer.score_actor(signals)

        # Step 2: Extract distinct signal families contributing to this evaluation
        triggered_families = SignalFamilyGate.extract_triggered_families(signals)

        # Step 3: Generate transparent evidence breakdown and mitigating factors
        evidence, counter_evidence = DecisionExplainer.generate_explanation(signals, gating_reasons)

        # Step 4: Map final gated level to platform policy action
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
