"""Tests for SafeFlow Milestone 6 Evaluation Framework & Ablations.

Validates:
1. Metric computation (Precision, Recall, F1, PR-AUC, ROC-AUC, P@k).
2. Prevalence reweighting formulas at 0.1%, 1.0%, and 5.0%.
3. Ablation studies across all 5 canonical configurations.
4. 3x3 Cross-platform transfer matrix.
5. End-to-end evaluation runner producing verifiable artifacts stamped with commit hash.
"""

from pathlib import Path
import numpy as np
import pytest

from safeflow.eval.metrics import (
    compute_all_metrics,
    prevalence_reweight,
    compute_precision_at_k,
    EvaluationMetrics,
)
from safeflow.eval.ablations import (
    AblationMode,
    AblationStudyRunner,
    get_ablation_features,
)
from safeflow.eval.transfer import CrossPlatformTransferMatrix
from safeflow.eval.runner import EvaluationRunner, get_git_commit_hash


def test_metric_computations_and_edge_cases():
    y_true = np.array([1, 1, 1, 0, 0, 0, 0, 0, 0, 0])
    y_scores = np.array([0.9, 0.8, 0.4, 0.7, 0.2, 0.1, 0.3, 0.1, 0.0, 0.05])

    metrics = compute_all_metrics(y_true, y_scores, threshold=0.50)
    assert metrics.sample_count == 10
    assert metrics.positive_count == 3
    assert metrics.negative_count == 7

    # At threshold 0.50: y_pred = [1, 1, 0, 1, 0, 0, 0, 0, 0, 0]
    # TP = 2, FP = 1, FN = 1, TN = 6
    # Precision = 2/3 ~ 0.6667, Recall = 2/3 ~ 0.6667
    assert metrics.precision == pytest.approx(0.6667, abs=1e-3)
    assert metrics.recall == pytest.approx(0.6667, abs=1e-3)
    assert metrics.f1 == pytest.approx(0.6667, abs=1e-3)
    assert metrics.roc_auc > 0.70
    assert metrics.pr_auc > 0.50

    # Precision @ k
    p_at_1 = compute_precision_at_k(y_true, y_scores, 1)
    p_at_2 = compute_precision_at_k(y_true, y_scores, 2)
    p_at_3 = compute_precision_at_k(y_true, y_scores, 3)
    assert p_at_1 == 1.0  # highest is 0.9 (idx 0, y=1)
    assert p_at_2 == 1.0  # 2nd is 0.8 (idx 1, y=1)
    assert p_at_3 == pytest.approx(2/3, abs=1e-3)  # 3rd is 0.7 (idx 3, y=0)


def test_prevalence_reweighting():
    # 90% recall, 1% FPR
    recall = 0.90
    fpr = 0.01

    # At 5% base rate
    p_5, f_5 = prevalence_reweight(recall, fpr, 0.05)
    # Precision = (0.05 * 0.90) / (0.05 * 0.90 + 0.95 * 0.01) = 0.045 / (0.045 + 0.0095) = 0.045 / 0.0545 ~ 0.8257
    assert p_5 == pytest.approx(0.8257, abs=1e-3)

    # At 0.1% base rate (high class imbalance)
    p_01, f_01 = prevalence_reweight(recall, fpr, 0.001)
    # Precision = (0.001 * 0.90) / (0.001 * 0.90 + 0.999 * 0.01) = 0.0009 / (0.0009 + 0.00999) = 0.0009 / 0.01089 ~ 0.0826
    assert p_01 == pytest.approx(0.0826, abs=1e-3)


def test_ablation_configurations_and_runner():
    # Test feature subsets
    full = get_ablation_features(AblationMode.FULL_SYSTEM)
    comments = get_ablation_features(AblationMode.COMMENT_ONLY)
    images = get_ablation_features(AblationMode.IMAGE_ONLY)
    links = get_ablation_features(AblationMode.LINK_ONLY)
    no_graph = get_ablation_features(AblationMode.NO_GRAPH)

    assert len(full) == 15
    assert all(f.startswith("text_") for f in comments)
    assert all(f.startswith("media_") for f in images)
    assert all(f.startswith("link_") or f.startswith("profile_") for f in links)
    assert "targeting_bipartite_risk" not in no_graph
    assert len(no_graph) == 14

    # Run synthetic ablation
    rng = np.random.RandomState(42)
    X_tr = rng.uniform(0.0, 1.0, size=(60, 15))
    y_tr = (rng.uniform(0.0, 1.0, size=60) > 0.7).astype(int)
    X_te = rng.uniform(0.0, 1.0, size=(40, 15))
    y_te = (rng.uniform(0.0, 1.0, size=40) > 0.7).astype(int)

    res = AblationStudyRunner.run_all_ablations(X_tr, y_tr, X_te, y_te)
    assert "full_system" in res
    assert "comment_only" in res
    assert "image_only" in res
    assert "link_only" in res
    assert "no_graph" in res
    for mode, m in res.items():
        assert isinstance(m, EvaluationMetrics)


def test_cross_platform_transfer_matrix():
    rng = np.random.RandomState(42)
    profiles = ["video_comments", "forum_communities", "chat_servers"]
    train_sets = {}
    eval_sets = {}

    for p in profiles:
        X_tr = rng.uniform(0.0, 1.0, size=(50, 15))
        y_tr = (rng.uniform(0.0, 1.0, size=50) > 0.7).astype(int)
        grp = np.arange(50)
        train_sets[p] = (X_tr, y_tr, grp)

        X_ev = rng.uniform(0.0, 1.0, size=(30, 15))
        y_ev = (rng.uniform(0.0, 1.0, size=30) > 0.7).astype(int)
        eval_sets[p] = (X_ev, y_ev)

    matrix = CrossPlatformTransferMatrix.compute(train_sets, eval_sets, profiles)
    assert len(matrix.matrix) == 9  # 3x3 = 9 cells
    md_table = matrix.to_markdown_table(metric="f1")
    assert "| Train Profile \\ Eval Profile |" in md_table
    assert "**video_comments**" in md_table
    assert "**forum_communities**" in md_table
    assert "**chat_servers**" in md_table


def test_end_to_end_benchmark_runner(tmp_path: Path):
    res = EvaluationRunner.run_benchmark(
        profile="video_comments",
        seed=42,
        actor_count=60,
        out_dir=tmp_path,
    )
    run_dir = Path(res["run_dir"])
    assert run_dir.exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "transfer_matrix.csv").exists()
    assert (run_dir / "summary.md").exists()

    summary_text = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert "SafeFlow Evaluation Report" in summary_text
    assert "Prevalence-Reweighted Performance" in summary_text
    assert "Component Ablation Studies" in summary_text
    assert "Cross-Platform Transfer Matrix" in summary_text
    assert get_git_commit_hash() in summary_text
