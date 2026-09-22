"""Calibrated statistical classifier for SafeFlow Decision Engine.

Trains a group-aware calibrated model (Logistic Regression with Platt/Sigmoid calibration)
on Variant A (development set) and scores unseen Variant B entities with strict family gating.
"""

from __future__ import annotations

from typing import Any, Sequence
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GroupKFold, StratifiedKFold

from safeflow.core.schema import RiskLevel, Signal
from safeflow.core.decision.gating import SignalFamilyGate


CANONICAL_FEATURE_ORDER = [
    "media_max_reuse",
    "media_suggestive_score",
    "media_ai_likelihood",
    "text_repetition_rate",
    "text_burst_velocity",
    "text_dormancy_anomaly",
    "targeting_percentile_conc",
    "targeting_bipartite_risk",
    "link_max_dest_risk",
    "link_chain_depth",
    "link_uses_shortener",
    "link_is_cloaked",
    "profile_homoglyph_density",
    "profile_bio_callout_score",
    "profile_edit_count",
]


FEATURE_ALIASES: dict[str, list[str]] = {
    "media_max_reuse": ["media_reuse_score", "media_max_reuse"],
    "media_suggestive_score": ["suggestive_presentation", "media_suggestive_score"],
    "media_ai_likelihood": ["ai_generated_identity_score", "ai_likelihood", "media_ai_likelihood"],
    "text_repetition_rate": ["text_repetition_rate", "duplicate_rate"],
    "text_burst_velocity": ["text_burst_velocity", "burst_velocity"],
    "text_dormancy_anomaly": ["text_dormancy_anomaly", "dormancy_anomaly"],
    "targeting_percentile_conc": ["space_popularity_concentration", "targeting_percentile_conc"],
    "targeting_bipartite_risk": ["targeting_risk_ratio", "targeting_bipartite_risk"],
    "link_max_dest_risk": ["link_destination_risk", "link_max_dest_risk"],
    "link_chain_depth": ["link_chain_depth", "redirect_depth"],
    "link_uses_shortener": ["link_uses_shortener"],
    "link_is_cloaked": ["link_is_cloaked", "cloaking_detected"],
    "profile_homoglyph_density": ["profile_homoglyph_density"],
    "profile_bio_callout_score": ["profile_bio_callout_score"],
    "profile_edit_count": ["profile_edit_count"],
}


class CalibratedScorer:
    """Statistical classifier with Platt scaling / Sigmoid calibration and group-aware cross-validation."""

    def __init__(self, feature_names: list[str] | None = None) -> None:
        self.feature_names = feature_names or list(CANONICAL_FEATURE_ORDER)
        self.model: CalibratedClassifierCV | LogisticRegression | None = None
        self.is_fitted: bool = False
        self.feature_weights: dict[str, float] = {}

    def extract_features_from_signals(self, signals: Sequence[Signal]) -> np.ndarray:
        """Map a collection of signals for an actor into a fixed-length feature vector."""
        feat_dict: dict[str, float] = {}
        for s in signals:
            feat_dict[s.name] = max(feat_dict.get(s.name, 0.0), s.value)

        vector = np.zeros(len(self.feature_names), dtype=np.float32)
        for idx, name in enumerate(self.feature_names):
            # Check exact match or aliases
            aliases = FEATURE_ALIASES.get(name, [name])
            val = max([feat_dict.get(a, 0.0) for a in aliases] + [0.0])
            vector[idx] = val
        return vector

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        groups: np.ndarray | None = None,
    ) -> "CalibratedScorer":
        """Fit calibrated logistic model with group-aware cross validation if groups are provided."""
        base_lr = LogisticRegression(
            C=1.0,
            max_iter=1000,
            random_state=42,
            class_weight="balanced",
        )

        n_samples = len(y)
        n_pos = int(np.sum(y == 1))
        n_neg = int(np.sum(y == 0))

        if n_samples < 10 or n_pos < 2 or n_neg < 2:
            # Fallback for single class or minimal samples
            base_lr.fit(X, y)
            self.model = base_lr
            self.is_fitted = True
            return self

        # Determine CV strategy
        valid_splits = None
        if groups is not None and len(np.unique(groups)) >= 3:
            k = min(3, len(np.unique(groups)))
            gkf = GroupKFold(n_splits=k)
            candidate_splits = list(gkf.split(X, y, groups=groups))
            # Check if all training folds contain at least 2 classes
            if all(len(np.unique(y[tr])) >= 2 for tr, te in candidate_splits):
                valid_splits = candidate_splits

        if valid_splits is None:
            k = max(2, min(3, min(n_pos, n_neg)))
            skf = StratifiedKFold(n_splits=k)
            valid_splits = list(skf.split(X, y))

        calibrated = CalibratedClassifierCV(
            estimator=base_lr,
            method="sigmoid",
            cv=valid_splits,
        )
        calibrated.fit(X, y)
        self.model = calibrated
        self.is_fitted = True

        # Extract average coefficients for explanation
        try:
            if hasattr(self.model, "calibrated_classifiers_"):
                coefs = np.mean(
                    [c.estimator.coef_[0] for c in self.model.calibrated_classifiers_],
                    axis=0,
                )
                self.feature_weights = dict(zip(self.feature_names, coefs.tolist()))
        except Exception:
            pass

        return self

    def score_actor(
        self,
        signals: Sequence[Signal],
    ) -> tuple[float, RiskLevel, list[str]]:
        """Predict calibrated risk probability and apply family gating.
        
        Returns:
            (calibrated_score_0_100, final_risk_level, gating_reasons)
        """
        if not self.is_fitted or self.model is None:
            # If not yet fitted, default to a heuristic fallback
            from safeflow.core.decision.heuristic import HeuristicScorer
            return HeuristicScorer().score_actor(signals)

        vec = self.extract_features_from_signals(signals).reshape(1, -1)
        proba = float(self.model.predict_proba(vec)[0, 1])
        score = proba * 100.0

        if score >= 70.0:
            raw_level = RiskLevel.CRITICAL
        elif score >= 45.0:
            raw_level = RiskLevel.HIGH
        elif score >= 20.0:
            raw_level = RiskLevel.MEDIUM
        else:
            raw_level = RiskLevel.LOW

        final_level, gating_reasons = SignalFamilyGate.apply_gating(
            raw_level=raw_level,
            raw_score=score,
            signals=signals,
        )

        return score, final_level, gating_reasons
