"""Cluster Evaluation and Negative-Control Separation Benchmark."""

from __future__ import annotations

from typing import Any
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from safeflow.core.schema import Actor


class ClusterEvaluator:
    """Evaluates detected graph clusters against ground-truth clusters and negative controls."""

    @classmethod
    def evaluate(
        cls,
        actors: list[Actor],
        detected_clusters: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Compute ARI, NMI, pairwise precision/recall, and legit negative control separation."""
        actor_to_detected: dict[str, str] = {}
        for c_name, members in detected_clusters.items():
            for m in members:
                actor_to_detected[m] = c_name

        # Extract ground truth
        y_true_labels: list[str] = []
        y_pred_labels: list[str] = []

        attack_actors: set[str] = set()
        legit_actors: set[str] = set()
        legit_fandom_actors: set[str] = set()
        legit_reuse_actors: set[str] = set()

        for a in actors:
            gt_dict = a.attributes.get("ground_truth", {})
            gt_cluster = gt_dict.get("cluster_id") or f"unclustered_{gt_dict.get('category', 'unknown')}_{a.actor_id}"
            det_cluster = actor_to_detected.get(a.actor_id, f"unclustered_pred_{a.actor_id}")

            y_true_labels.append(gt_cluster)
            y_pred_labels.append(det_cluster)

            cat = gt_dict.get("category", "")
            if gt_dict.get("is_attack"):
                attack_actors.add(a.actor_id)
            else:
                legit_actors.add(a.actor_id)
                if cat == "LEGIT_FANDOM":
                    legit_fandom_actors.add(a.actor_id)
                elif cat == "LEGIT_AVATAR_REUSE":
                    legit_reuse_actors.add(a.actor_id)

        # 1. Standard Clustering Metrics
        ari = float(adjusted_rand_score(y_true_labels, y_pred_labels))
        nmi = float(normalized_mutual_info_score(y_true_labels, y_pred_labels))

        # 2. Pairwise Precision and Recall on Attack Pairs
        # Ground-truth attack pairs
        gt_pairs: set[tuple[str, str]] = set()
        for i, a1 in enumerate(actors):
            gt1 = a1.attributes.get("ground_truth", {}).get("cluster_id")
            if not gt1:
                continue
            for a2 in actors[i + 1:]:
                gt2 = a2.attributes.get("ground_truth", {}).get("cluster_id")
                if gt1 == gt2:
                    gt_pairs.add((min(a1.actor_id, a2.actor_id), max(a1.actor_id, a2.actor_id)))

        # Detected pairs
        det_pairs: set[tuple[str, str]] = set()
        for members in detected_clusters.values():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    m1, m2 = members[i], members[j]
                    det_pairs.add((min(m1, m2), max(m1, m2)))

        tp = len(gt_pairs.intersection(det_pairs))
        fp = len(det_pairs - gt_pairs)
        fn = len(gt_pairs - det_pairs)

        pairwise_precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        pairwise_recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        # 3. Negative Control Separation Check:
        # Check if legit fandom or legit reuse actors are wrongfully merged into attack clusters
        attack_cluster_names: set[str] = set()
        for c_name, members in detected_clusters.items():
            if any(m in attack_actors for m in members):
                attack_cluster_names.add(c_name)

        fandom_false_merges = 0
        for m in legit_fandom_actors:
            c_name = actor_to_detected.get(m)
            if c_name and c_name in attack_cluster_names:
                fandom_false_merges += 1

        reuse_false_merges = 0
        for m in legit_reuse_actors:
            c_name = actor_to_detected.get(m)
            if c_name and c_name in attack_cluster_names:
                reuse_false_merges += 1

        return {
            "ari": round(ari, 4),
            "nmi": round(nmi, 4),
            "pairwise_precision": round(pairwise_precision, 4),
            "pairwise_recall": round(pairwise_recall, 4),
            "total_detected_clusters": len(detected_clusters),
            "fandom_false_merges": fandom_false_merges,
            "avatar_reuse_false_merges": reuse_false_merges,
        }
