"""Cross-Platform Transfer Matrix evaluator for SafeFlow."""

from __future__ import annotations

from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from safeflow.eval.metrics import EvaluationMetrics, compute_all_metrics
from safeflow.core.decision.calibrated import CalibratedScorer


class TransferCell(BaseModel):
    model_config = ConfigDict(extra="forbid")
    train_profile: str
    eval_profile: str
    metrics: EvaluationMetrics


class CrossPlatformTransferMatrix(BaseModel):
    """3x3 Transfer Matrix across platform profiles."""
    model_config = ConfigDict(extra="forbid")

    profiles: list[str] = Field(
        default_factory=lambda: ["video_comments", "forum_communities", "chat_servers"]
    )
    matrix: list[TransferCell] = Field(default_factory=list)

    def get_f1_matrix(self) -> dict[str, dict[str, float]]:
        res: dict[str, dict[str, float]] = {p: {} for p in self.profiles}
        for cell in self.matrix:
            res[cell.train_profile][cell.eval_profile] = cell.metrics.f1
        return res

    def to_markdown_table(self, metric: str = "f1") -> str:
        header = f"| Train Profile \\ Eval Profile | " + " | ".join(self.profiles) + " |"
        sep = "|" + "---|" * (len(self.profiles) + 1)
        lines = [header, sep]

        for tr_p in self.profiles:
            row = [f"**{tr_p}**"]
            for ev_p in self.profiles:
                cell = next(
                    (c for c in self.matrix if c.train_profile == tr_p and c.eval_profile == ev_p),
                    None,
                )
                if cell:
                    val = getattr(cell.metrics, metric, 0.0)
                    row.append(f"{val:.4f}")
                else:
                    row.append("N/A")
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    @classmethod
    def compute(
        cls,
        datasets: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray | None]],
        eval_datasets: dict[str, tuple[np.ndarray, np.ndarray]],
        profiles: list[str] | None = None,
    ) -> CrossPlatformTransferMatrix:
        prof_list = profiles or ["video_comments", "forum_communities", "chat_servers"]
        cells: list[TransferCell] = []

        trained_models: dict[str, CalibratedScorer] = {}
        for tr_p in prof_list:
            if tr_p not in datasets:
                continue
            X_tr, y_tr, grp_tr = datasets[tr_p]
            scorer = CalibratedScorer()
            scorer.fit(X_tr, y_tr, groups=grp_tr)
            trained_models[tr_p] = scorer

        for tr_p in prof_list:
            scorer = trained_models.get(tr_p)
            if not scorer:
                continue
            for ev_p in prof_list:
                if ev_p not in eval_datasets:
                    continue
                X_ev, y_ev = eval_datasets[ev_p]
                y_scores = scorer.model.predict_proba(X_ev)[:, 1]
                metrics = compute_all_metrics(y_ev, y_scores)
                cells.append(
                    TransferCell(
                        train_profile=tr_p,
                        eval_profile=ev_p,
                        metrics=metrics,
                    )
                )

        return cls(profiles=prof_list, matrix=cells)
