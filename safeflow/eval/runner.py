"""Evaluation benchmark runner and report generator for SafeFlow."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Literal
import numpy as np

from safeflow.adapters.synthetic.generator import SyntheticGenerator, SyntheticDataset
from safeflow.adapters.synthetic.models import AttackCategory, GeneratorConfig
from safeflow.eval.metrics import EvaluationMetrics, compute_all_metrics
from safeflow.eval.ablations import AblationStudyRunner
from safeflow.eval.transfer import CrossPlatformTransferMatrix
from safeflow.core.decision.calibrated import CANONICAL_FEATURE_ORDER, CalibratedScorer
from safeflow.core.decision.engine import DecisionEngine
from safeflow.core.graph.builder import HeterogeneousGraphBuilder
from safeflow.core.graph.bipartite import BipartiteCoTargetingEngine
from safeflow.core.graph.clustering import CoordinationClusteringEngine

from safeflow.plugins.media_reuse import MediaReusePlugin
from safeflow.plugins.text_behavior import TextBehaviorPlugin
from safeflow.plugins.targeting import TargetingPlugin
from safeflow.plugins.link_destination import LinkDestinationPlugin
from safeflow.plugins.actor_profile import ActorProfilePlugin


def get_git_commit_hash() -> str:
    """Get current git commit hash for report stamping."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()[:8]
    except Exception:
        return "uncommitted"


def extract_features_and_labels(
    dataset: SyntheticDataset,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Extract feature matrix X, binary labels y, cluster groups, and actor_ids from a dataset."""
    plugins = [
        MediaReusePlugin(),
        TextBehaviorPlugin(),
        TargetingPlugin(),
        LinkDestinationPlugin(),
        ActorProfilePlugin(),
    ]

    ctx = {
        "actors": dataset.actors,
        "content": dataset.content,
        "media": dataset.media,
        "spaces": dataset.spaces,
        "links": dataset.links,
    }

    all_signals = []
    for p in plugins:
        res = p.run(batch=dataset.actors, context=ctx)
        all_signals.extend(res)

    # Graph and clustering analysis
    G = HeterogeneousGraphBuilder.build(
        actors=dataset.actors,
        spaces=dataset.spaces,
        contents=dataset.content,
        media=dataset.media,
        links=dataset.links,
    )
    actor_sim_graph = CoordinationClusteringEngine.build_actor_similarity_graph(G)
    detected_clusters = CoordinationClusteringEngine.detect_clusters(actor_sim_graph, min_cluster_size=2)

    # Build cluster map
    actor_cluster_map: dict[str, int] = {}
    for cluster_idx, (c_name, actor_list) in enumerate(detected_clusters.items()):
        for aid in actor_list:
            actor_cluster_map[aid] = cluster_idx + 1

    # Map signals per actor
    actor_signals_map: dict[str, list[Any]] = {a.actor_id: [] for a in dataset.actors}
    for s in all_signals:
        if s.subject_type == "actor" and s.subject_id in actor_signals_map:
            actor_signals_map[s.subject_id].append(s)

    # Build numpy arrays
    n_actors = len(dataset.actors)
    n_features = len(CANONICAL_FEATURE_ORDER)
    X = np.zeros((n_actors, n_features), dtype=np.float32)
    y = np.zeros(n_actors, dtype=np.int32)
    groups = np.zeros(n_actors, dtype=np.int32)
    actor_ids = []
    scorer = CalibratedScorer()

    for idx, actor in enumerate(dataset.actors):
        actor_ids.append(actor.actor_id)
        sigs = actor_signals_map[actor.actor_id]
        X[idx, :] = scorer.extract_features_from_signals(sigs)

        gt = dataset.ground_truth.get(actor.actor_id)
        if gt:
            y[idx] = 1 if gt.is_attack else 0
            if gt.is_attack and gt.cluster_id:
                groups[idx] = hash(gt.cluster_id) % 100000 + 1
            else:
                groups[idx] = actor_cluster_map.get(actor.actor_id, idx + 1)
        else:
            groups[idx] = idx + 1

    return X, y, groups, actor_ids


class EvaluationRunner:
    """Executes benchmark runs and outputs structured results."""

    @classmethod
    def run_benchmark(
        cls,
        profile: str = "video_comments",
        seed: int = 42,
        actor_count: int = 200,
        out_dir: str | Path = "results",
    ) -> dict[str, Any]:
        """Run full train-on-A, eval-on-B benchmark with ablations and transfer matrix."""
        out_path = Path(out_dir)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"eval_{profile}_{timestamp}"
        run_dir = out_path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        commit_hash = get_git_commit_hash()

        # 1. Generate Development Set (Variant A)
        cfg_a = GeneratorConfig(
            seed=seed,
            variant="A",
            platform_profile=profile,  # type: ignore[arg-type]
            actor_count=actor_count,
        )
        ds_a = SyntheticGenerator(cfg_a).generate()
        X_a, y_a, grp_a, _ = extract_features_and_labels(ds_a)

        # 2. Generate Held-Out Evaluation Set (Variant B)
        cfg_b = GeneratorConfig(
            seed=seed + 100,
            variant="B",
            platform_profile=profile,  # type: ignore[arg-type]
            actor_count=actor_count,
        )
        ds_b = SyntheticGenerator(cfg_b).generate()
        X_b, y_b, _, _ = extract_features_and_labels(ds_b)

        # 3. Fit Calibrated Model on Variant A
        scorer = CalibratedScorer()
        scorer.fit(X_a, y_a, groups=grp_a)

        # 4. Evaluate on Variant B
        y_scores_b = scorer.model.predict_proba(X_b)[:, 1]
        overall_metrics = compute_all_metrics(y_b, y_scores_b)

        # 5. Run Ablations
        ablations = AblationStudyRunner.run_all_ablations(
            X_train=X_a,
            y_train=y_a,
            X_test=X_b,
            y_test=y_b,
            groups_train=grp_a,
        )

        # 6. Compute Cross-Platform Transfer Matrix
        profiles = ["video_comments", "forum_communities", "chat_servers"]
        train_sets: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray | None]] = {}
        eval_sets: dict[str, tuple[np.ndarray, np.ndarray]] = {}

        for p in profiles:
            if p == profile:
                train_sets[p] = (X_a, y_a, grp_a)
                eval_sets[p] = (X_b, y_b)
            else:
                cfg_p_a = GeneratorConfig(seed=seed, variant="A", platform_profile=p, actor_count=80)  # type: ignore[arg-type]
                ds_p_a = SyntheticGenerator(cfg_p_a).generate()
                X_pa, y_pa, grp_pa, _ = extract_features_and_labels(ds_p_a)
                train_sets[p] = (X_pa, y_pa, grp_pa)

                cfg_p_b = GeneratorConfig(seed=seed + 100, variant="B", platform_profile=p, actor_count=80)  # type: ignore[arg-type]
                ds_p_b = SyntheticGenerator(cfg_p_b).generate()
                X_pb, y_pb, _, _ = extract_features_and_labels(ds_p_b)
                eval_sets[p] = (X_pb, y_pb)

        transfer_matrix = CrossPlatformTransferMatrix.compute(
            datasets=train_sets,
            eval_datasets=eval_sets,
            profiles=profiles,
        )

        # Export Files
        # 1. metrics.json
        metrics_dict = {
            "run_id": run_id,
            "commit_hash": commit_hash,
            "timestamp": timestamp,
            "profile": profile,
            "seed": seed,
            "variant_train": "A",
            "variant_eval": "B",
            "overall_metrics": overall_metrics.model_dump(),
            "ablations": {k: v.model_dump() for k, v in ablations.items()},
        }
        with open(run_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2)

        # 2. transfer_matrix.csv
        csv_lines = ["train_profile," + ",".join(profiles)]
        f1_map = transfer_matrix.get_f1_matrix()
        for tr_p in profiles:
            row = [tr_p] + [f"{f1_map[tr_p].get(ev_p, 0.0):.4f}" for ev_p in profiles]
            csv_lines.append(",".join(row))

        with open(run_dir / "transfer_matrix.csv", "w", encoding="utf-8") as f:
            f.write("\n".join(csv_lines))

        # 3. summary.md
        summary_md = f"""# SafeFlow Evaluation Report: `{profile}`

- **Run ID**: `{run_id}`
- **Git Commit**: `{commit_hash}`
- **Evaluation Date**: {datetime.now(timezone.utc).isoformat()}
- **Platform Profile**: `{profile}`
- **Training Set**: Variant A (Seed {seed})
- **Held-Out Test Set**: Variant B (Seed {seed + 100})

## 1. Overall Performance (Variant B Held-Out)

| Metric | Score |
|---|---|
| **Precision** | {overall_metrics.precision:.4f} |
| **Recall** | {overall_metrics.recall:.4f} |
| **F1 Score** | {overall_metrics.f1:.4f} |
| **PR-AUC (Avg Precision)** | {overall_metrics.pr_auc:.4f} |
| **ROC-AUC** | {overall_metrics.roc_auc:.4f} |
| **Precision @ 10** | {overall_metrics.precision_at_10:.4f} |
| **Precision @ 50** | {overall_metrics.precision_at_50:.4f} |
| **Precision @ 100** | {overall_metrics.precision_at_100:.4f} |

## 2. Prevalence-Reweighted Performance

| Target Base Rate | Adjusted Precision | Adjusted F1 | Expected FPR |
|---|---|---|---|
"""
        for adj in overall_metrics.prevalence_adjustments:
            summary_md += f"| **{adj.base_rate * 100:.1f}%** | {adj.adjusted_precision:.4f} | {adj.adjusted_f1:.4f} | {adj.expected_fpr:.4f} |\n"

        summary_md += f"""
## 3. Component Ablation Studies

| Ablation Mode | F1 Score | PR-AUC | ROC-AUC | Precision | Recall |
|---|---|---|---|---|---|
"""
        for mode_name, m in ablations.items():
            summary_md += f"| **{mode_name}** | {m.f1:.4f} | {m.pr_auc:.4f} | {m.roc_auc:.4f} | {m.precision:.4f} | {m.recall:.4f} |\n"

        summary_md += f"""
## 4. Cross-Platform Transfer Matrix (F1 Score)

{transfer_matrix.to_markdown_table(metric='f1')}
"""

        with open(run_dir / "summary.md", "w", encoding="utf-8") as f:
            f.write(summary_md)

        return {
            "run_dir": str(run_dir),
            "metrics": overall_metrics,
            "ablations": ablations,
            "transfer_matrix": transfer_matrix,
        }
