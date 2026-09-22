"""Ablation study generator and evaluator for SafeFlow."""

from __future__ import annotations

from enum import Enum
from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from safeflow.eval.metrics import EvaluationMetrics, compute_all_metrics
from safeflow.core.decision.calibrated import CANONICAL_FEATURE_ORDER, CalibratedScorer


class AblationMode(str, Enum):
    FULL_SYSTEM = "full_system"
    COMMENT_ONLY = "comment_only"
    IMAGE_ONLY = "image_only"
    LINK_ONLY = "link_only"
    NO_GRAPH = "no_graph"


class AblationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: AblationMode
    active_features: list[str]


def get_ablation_features(mode: AblationMode) -> list[str]:
    """Return the active feature subset for a given ablation mode."""
    if mode == AblationMode.FULL_SYSTEM:
        return list(CANONICAL_FEATURE_ORDER)

    elif mode == AblationMode.COMMENT_ONLY:
        return [
            f for f in CANONICAL_FEATURE_ORDER
            if f.startswith("text_")
        ]

    elif mode == AblationMode.IMAGE_ONLY:
        return [
            f for f in CANONICAL_FEATURE_ORDER
            if f.startswith("media_")
        ]

    elif mode == AblationMode.LINK_ONLY:
        return [
            f for f in CANONICAL_FEATURE_ORDER
            if f.startswith("link_") or f.startswith("profile_")
        ]

    elif mode == AblationMode.NO_GRAPH:
        return [
            f for f in CANONICAL_FEATURE_ORDER
            if f != "targeting_bipartite_risk"
        ]

    return list(CANONICAL_FEATURE_ORDER)


class AblationStudyRunner:
    """Executes ablation studies on feature matrices."""

    @classmethod
    def run_all_ablations(
        cls,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: list[str] | None = None,
        groups_train: np.ndarray | None = None,
    ) -> dict[str, EvaluationMetrics]:
        all_features = feature_names or list(CANONICAL_FEATURE_ORDER)
        results: dict[str, EvaluationMetrics] = {}

        for mode in AblationMode:
            active_feats = get_ablation_features(mode)
            feature_indices = [
                i for i, name in enumerate(all_features)
                if name in active_feats
            ]

            if not feature_indices:
                continue

            X_tr_sub = X_train[:, feature_indices]
            X_te_sub = X_test[:, feature_indices]

            scorer = CalibratedScorer(feature_names=active_feats)
            scorer.fit(X_tr_sub, y_train, groups=groups_train)

            # Predict probabilities on test set
            y_scores = scorer.model.predict_proba(X_te_sub)[:, 1]
            metrics = compute_all_metrics(y_test, y_scores)
            results[mode.value] = metrics

        return results
