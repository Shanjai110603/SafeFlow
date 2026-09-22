"""Standardized evaluation metrics for SafeFlow benchmarks.

Computes Precision, Recall, F1, PR-AUC, ROC-AUC, Precision@k,
and mathematical prevalence-reweighted metrics at 0.1%, 1.0%, and 5.0% base rates.
"""

from __future__ import annotations

from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)


class PrevalenceReweightedMetrics(BaseModel):
    """Metrics adjusted for a specific real-world base rate prevalence."""
    model_config = ConfigDict(extra="forbid")

    base_rate: float = Field(..., description="Hypothetical real-world base rate prevalence (e.g. 0.001, 0.01, 0.05)")
    adjusted_precision: float
    adjusted_f1: float
    expected_fpr: float


class EvaluationMetrics(BaseModel):
    """Comprehensive benchmark evaluation metrics."""
    model_config = ConfigDict(extra="forbid")

    sample_count: int
    positive_count: int
    negative_count: int
    threshold: float = 0.50
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    precision_at_10: float
    precision_at_50: float
    precision_at_100: float
    prevalence_adjustments: list[PrevalenceReweightedMetrics] = Field(default_factory=list)


def prevalence_reweight(
    recall: float,
    fpr: float,
    target_base_rate: float,
) -> tuple[float, float]:
    """Calculate mathematically adjusted Precision and F1 under a target base rate.
    
    Precision = (base_rate * recall) / (base_rate * recall + (1 - base_rate) * fpr)
    """
    numerator = target_base_rate * recall
    denominator = numerator + (1.0 - target_base_rate) * fpr
    if denominator <= 0.0:
        adj_precision = 0.0
    else:
        adj_precision = min(1.0, max(0.0, numerator / denominator))

    if (adj_precision + recall) <= 0.0:
        adj_f1 = 0.0
    else:
        adj_f1 = 2.0 * (adj_precision * recall) / (adj_precision + recall)

    return adj_precision, adj_f1


def compute_precision_at_k(y_true: np.ndarray, y_scores: np.ndarray, k: int) -> float:
    """Compute precision among the top-k highest ranked predictions."""
    if len(y_scores) == 0 or k <= 0:
        return 0.0
    k = min(k, len(y_scores))
    top_k_indices = np.argsort(y_scores)[::-1][:k]
    return float(np.mean(y_true[top_k_indices]))


def compute_all_metrics(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    threshold: float = 0.50,
) -> EvaluationMetrics:
    """Calculate all standard and prevalence-reweighted evaluation metrics."""
    y_true = np.asarray(y_true, dtype=int)
    y_scores = np.asarray(y_scores, dtype=float)
    y_pred = (y_scores >= threshold).astype(int)

    n_samples = len(y_true)
    n_pos = int(np.sum(y_true == 1))
    n_neg = int(np.sum(y_true == 0))

    if n_pos == 0 or n_neg == 0:
        return EvaluationMetrics(
            sample_count=n_samples,
            positive_count=n_pos,
            negative_count=n_neg,
            threshold=threshold,
            precision=1.0 if n_pos == 0 and np.sum(y_pred) == 0 else 0.0,
            recall=0.0,
            f1=0.0,
            roc_auc=0.50,
            pr_auc=0.0,
            precision_at_10=0.0,
            precision_at_50=0.0,
            precision_at_100=0.0,
            prevalence_adjustments=[],
        )

    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    try:
        roc_auc = float(roc_auc_score(y_true, y_scores))
    except Exception:
        roc_auc = 0.50

    try:
        pr_auc = float(average_precision_score(y_true, y_scores))
    except Exception:
        pr_auc = float(n_pos / n_samples)

    # Compute False Positive Rate (FPR) = FP / (FP + TN)
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    p_at_10 = compute_precision_at_k(y_true, y_scores, 10)
    p_at_50 = compute_precision_at_k(y_true, y_scores, 50)
    p_at_100 = compute_precision_at_k(y_true, y_scores, 100)

    # Calculate prevalence reweighted metrics for 0.1%, 1.0%, and 5.0%
    prevalence_adjustments = []
    for base_rate in [0.001, 0.01, 0.05]:
        adj_p, adj_f = prevalence_reweight(rec, fpr, base_rate)
        prevalence_adjustments.append(
            PrevalenceReweightedMetrics(
                base_rate=base_rate,
                adjusted_precision=round(adj_p, 4),
                adjusted_f1=round(adj_f, 4),
                expected_fpr=round(fpr, 4),
            )
        )

    return EvaluationMetrics(
        sample_count=n_samples,
        positive_count=n_pos,
        negative_count=n_neg,
        threshold=threshold,
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        roc_auc=round(roc_auc, 4),
        pr_auc=round(pr_auc, 4),
        precision_at_10=round(p_at_10, 4),
        precision_at_50=round(p_at_50, 4),
        precision_at_100=round(p_at_100, 4),
        prevalence_adjustments=prevalence_adjustments,
    )
