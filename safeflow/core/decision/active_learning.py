"""Active Learning & Appeals-to-Calibration Feedback Loop.

Integrates human-in-the-loop analyst decisions and overturned appeals
into the CalibratedScorer via continuous sample reweighting and retraining.
"""

from __future__ import annotations

from typing import Any
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from safeflow.core.database import AppealRecord
from safeflow.core.decision.calibrated import CalibratedScorer


class ActiveLearningPipeline:
    """Manages active-learning retraining from resolved moderation appeals."""

    @classmethod
    def extract_appeal_feedback(cls, session: Session) -> list[dict[str, Any]]:
        """Query resolved appeals to extract labeled supervision samples."""
        stmt = select(AppealRecord).where(AppealRecord.status.in_(["OVERTURNED", "UPHELD"]))
        records = session.execute(stmt).scalars().all()

        feedback_samples: list[dict[str, Any]] = []
        for r in records:
            # OVERTURNED means false positive -> ground truth label is 0 (benign)
            # UPHELD means true positive -> ground truth label is 1 (attack)
            label = 0 if r.status == "OVERTURNED" else 1
            feedback_samples.append({
                "appeal_id": r.appeal_id,
                "actor_id": r.actor_id,
                "media_id": r.media_id,
                "status": r.status,
                "target_label": label,
                "weight": 2.0 if r.status == "OVERTURNED" else 1.5,  # Higher weight on false positives to reduce creator friction
            })

        return feedback_samples

    @classmethod
    def retrain_with_feedback(
        cls,
        scorer: CalibratedScorer,
        base_features: np.ndarray,
        base_labels: np.ndarray,
        feedback_features: np.ndarray,
        feedback_labels: np.ndarray,
        feedback_weights: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """Retrain CalibratedScorer by augmenting base benchmark data with appeal feedback."""
        if feedback_features.shape[0] == 0:
            return {"status": "NO_FEEDBACK_AVAILABLE", "samples_added": 0}

        # Combine datasets
        combined_X = np.vstack([base_features, feedback_features])
        combined_y = np.concatenate([base_labels, feedback_labels])

        # Construct sample weights (1.0 for base, custom for feedback)
        base_weights = np.ones(base_features.shape[0], dtype=np.float64)
        if feedback_weights is None:
            feedback_weights = np.full(feedback_features.shape[0], 2.0, dtype=np.float64)
        combined_weights = np.concatenate([base_weights, feedback_weights])

        # Create dummy group indices if needed
        dummy_groups = np.arange(combined_X.shape[0])

        # Retrain model
        scorer.fit(combined_X, combined_y, groups=dummy_groups)

        return {
            "status": "RETRAINED",
            "samples_added": int(feedback_features.shape[0]),
            "total_samples": int(combined_X.shape[0]),
            "updated_weights": {k: float(v) for k, v in scorer.feature_weights.items()},
        }
