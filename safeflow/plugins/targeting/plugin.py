"""Targeting and Space Concentration SignalPlugin."""

from __future__ import annotations

from collections import Counter
from typing import Any
from pydantic import BaseModel, Field
from safeflow.core.schema import Actor, Content, Signal, Space
from safeflow.plugins.base import BaseSignalPlugin


class TargetingConfig(BaseModel):
    high_popularity_percentile_cutoff: float = Field(default=80.0, description="Percentile above which a space is considered high popularity")
    risk_ratio_threshold: float = Field(default=2.5, description="Observed vs expected joint targeting ratio threshold")


class TargetingPlugin(BaseSignalPlugin):
    """Measures actor concentration on high-popularity spaces and bipartite co-targeting risk ratios."""

    name: str = "targeting"
    family: str = "TARGETING"
    version: str = "1.0.0"
    requires: list[str] = ["actor", "content", "space"]

    def __init__(self, config: TargetingConfig | None = None):
        self.config = config or TargetingConfig()

    def get_config_schema(self) -> type[BaseModel]:
        return TargetingConfig

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        signals: list[Signal] = []
        ctx = context or {}

        actors: list[Actor] = [item for item in batch if isinstance(item, Actor)] + ctx.get("actors", [])
        contents: list[Content] = [item for item in batch if isinstance(item, Content)] + ctx.get("content", [])
        spaces: list[Space] = [item for item in batch if isinstance(item, Space)] + ctx.get("spaces", [])

        if not actors or not spaces:
            return signals

        # Map spaces by space_id
        space_by_id = {s.space_id: s for s in spaces}
        total_spaces = len(spaces)

        # Map content to actor
        actor_spaces: dict[str, list[str]] = {a.actor_id: [] for a in actors}
        for c in contents:
            if c.actor_id in actor_spaces and c.space_id in space_by_id:
                actor_spaces[c.actor_id].append(c.space_id)

        # Compute platform-wide space targeting frequencies
        space_comment_counts: Counter[str] = Counter()
        total_comments = len(contents) or 1
        for c in contents:
            space_comment_counts[c.space_id] += 1

        for a in actors:
            targeted_space_ids = actor_spaces.get(a.actor_id, [])
            if not targeted_space_ids:
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="space_popularity_concentration",
                        value=0.0,
                        confidence=0.5,
                        evidence_refs=[],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )
                continue

            # 1. Platform-Normalized Space Popularity Concentration
            percentiles = [space_by_id[s_id].popularity.percentile for s_id in targeted_space_ids if s_id in space_by_id]
            avg_percentile = sum(percentiles) / len(percentiles) if percentiles else 50.0

            # Normalized concentration score (0.0 to 1.0)
            # High score if actor exclusively targets spaces in the 90th+ percentile
            concentration_score = max(0.0, min(1.0, (avg_percentile - 50.0) / 45.0)) if avg_percentile > 50.0 else 0.0

            # 2. Risk Ratio (Observed vs Expected Chance)
            # RCAT philosophy: measure whether an actor's targeting of top spaces significantly exceeds chance
            high_pop_spaces = [s_id for s_id in targeted_space_ids if space_by_id.get(s_id) and space_by_id[s_id].popularity.percentile >= self.config.high_popularity_percentile_cutoff]
            observed_high_pop_rate = len(high_pop_spaces) / max(1, len(targeted_space_ids))

            # Expected platform baseline rate
            high_pop_total_spaces = sum(1 for s in spaces if s.popularity.percentile >= self.config.high_popularity_percentile_cutoff)
            expected_baseline_rate = max(0.05, high_pop_total_spaces / max(1, total_spaces))

            risk_ratio = observed_high_pop_rate / expected_baseline_rate
            # Normalize risk ratio (e.g. ratio of 1.0 -> 0.0, ratio of 3.0+ -> 1.0)
            normalized_risk_ratio = max(0.0, min(1.0, (risk_ratio - 1.0) / 2.5)) if risk_ratio > 1.0 else 0.0

            evidence = list(set(targeted_space_ids))[:5]

            signals.append(
                Signal(
                    subject_type="actor",
                    subject_id=a.actor_id,
                    family=self.family,
                    name="space_popularity_concentration",
                    value=round(concentration_score, 4),
                    confidence=0.85,
                    evidence_refs=evidence,
                    producer=self.name,
                    producer_version=self.version,
                )
            )

            signals.append(
                Signal(
                    subject_type="actor",
                    subject_id=a.actor_id,
                    family=self.family,
                    name="targeting_risk_ratio",
                    value=round(normalized_risk_ratio, 4),
                    confidence=0.80,
                    evidence_refs=evidence,
                    producer=self.name,
                    producer_version=self.version,
                )
            )

        return signals
