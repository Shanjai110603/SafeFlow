"""Text and Temporal Trajectory Behavior SignalPlugin."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import math
import re
from typing import Any
from pydantic import BaseModel, Field
from safeflow.core.schema import Actor, Content, Signal
from safeflow.plugins.base import BaseSignalPlugin


class TextBehaviorConfig(BaseModel):
    min_comments_for_analysis: int = Field(default=2, description="Minimum comments required for trajectory analysis")
    dormancy_threshold_days: float = Field(default=90.0, description="Dormancy age indicating aged/dormant account")


def _tokenize(text: str) -> list[str]:
    """Simple alphanumeric tokenizer."""
    return re.findall(r"\b\w+\b", text.lower())


def _tfidf_cosine_sim(texts: list[str]) -> float:
    """Compute average pairwise cosine similarity using pure-Python TF-IDF representation."""
    if len(texts) < 2:
        return 0.0

    docs = [_tokenize(t) for t in texts]
    all_terms = set(term for doc in docs for term in doc)
    if not all_terms:
        return 0.0

    # Document frequency
    df: Counter[str] = Counter()
    for doc in docs:
        for term in set(doc):
            df[term] += 1

    num_docs = len(docs)
    vectors = []
    for doc in docs:
        tf = Counter(doc)
        doc_len = len(doc) or 1
        vec = {}
        norm_sq = 0.0
        for term, count in tf.items():
            idf = math.log(1.0 + num_docs / (1.0 + df[term]))
            val = (count / doc_len) * idf
            vec[term] = val
            norm_sq += val * val
        norm = math.sqrt(norm_sq) or 1.0
        vectors.append({t: v / norm for t, v in vec.items()})

    # Average pairwise similarity
    total_sim = 0.0
    pairs = 0
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            v1, v2 = vectors[i], vectors[j]
            # Dot product
            dot = sum(val * v2.get(t, 0.0) for t, val in v1.items())
            total_sim += dot
            pairs += 1

    return total_sim / pairs if pairs > 0 else 0.0


class TextBehaviorPlugin(BaseSignalPlugin):
    """Analyzes text repetition, burst velocity, lexical diversity, and temporal trajectories."""

    name: str = "text_behavior"
    family: str = "BEHAVIOR"
    version: str = "1.0.0"
    requires: list[str] = ["actor", "content"]

    def __init__(self, config: TextBehaviorConfig | None = None):
        self.config = config or TextBehaviorConfig()

    def get_config_schema(self) -> type[BaseModel]:
        return TextBehaviorConfig

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        signals: list[Signal] = []
        ctx = context or {}

        actors: list[Actor] = [item for item in batch if isinstance(item, Actor)] + ctx.get("actors", [])
        contents: list[Content] = [item for item in batch if isinstance(item, Content)] + ctx.get("content", [])

        if not actors:
            return signals

        # Group contents by actor_id
        content_by_actor: dict[str, list[Content]] = {a.actor_id: [] for a in actors}
        for c in contents:
            if c.actor_id in content_by_actor:
                content_by_actor[c.actor_id].append(c)

        for a in actors:
            actor_contents = sorted(content_by_actor.get(a.actor_id, []), key=lambda x: x.created_at)
            c_count = len(actor_contents)

            if c_count < self.config.min_comments_for_analysis:
                # Insufficient volume for behavioral anomaly
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="comment_anomaly_score",
                        value=0.0,
                        confidence=0.5,
                        evidence_refs=[c.content_id for c in actor_contents],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )
                continue

            texts = [c.text for c in actor_contents]
            tokens_all = [t for text in texts for t in _tokenize(text)]

            # 1. Lexical Diversity (TTR - Type Token Ratio)
            unique_tokens = set(tokens_all)
            ttr = len(unique_tokens) / max(1, len(tokens_all))
            # Low TTR indicates robotic repetition
            lexical_anomaly = max(0.0, 1.0 - (ttr / 0.8))

            # 2. Duplicate / Repeated Exact Phrase Rate
            text_counts = Counter(texts)
            duplicate_fraction = sum(cnt - 1 for cnt in text_counts.values()) / max(1, c_count)

            # 3. TF-IDF Semantic Similarity across comments
            sim_score = _tfidf_cosine_sim(texts)

            # 4. Burst Velocity (seconds between consecutive comments)
            deltas: list[float] = []
            for i in range(1, c_count):
                diff = (actor_contents[i].created_at - actor_contents[i - 1].created_at).total_seconds()
                deltas.append(max(0.1, diff))

            avg_delta = sum(deltas) / len(deltas) if deltas else 3600.0
            # If average interval is under 60 seconds, burst velocity is high
            burst_velocity = max(0.0, min(1.0, 1.0 - (avg_delta / 120.0))) if avg_delta < 120.0 else 0.0

            # 5. Temporal Trajectory Features (Sentinel-style: Dormancy Transition)
            # Compare actor account creation to first comment timestamp
            first_c_time = actor_contents[0].created_at
            account_dormancy_days = (first_c_time - a.created_at).total_seconds() / 86400.0
            sudden_dormant_activation = 1.0 if (account_dormancy_days >= self.config.dormancy_threshold_days and burst_velocity > 0.4) else 0.0

            # Composite comment anomaly score
            # Note: A curiosity funnel with genuinely conversational/diverse comments will have LOW semantic similarity and HIGH TTR
            composite_comment_anomaly = (
                0.35 * duplicate_fraction +
                0.35 * sim_score +
                0.30 * burst_velocity
            )

            evidence = [c.content_id for c in actor_contents[:5]]

            signals.append(
                Signal(
                    subject_type="actor",
                    subject_id=a.actor_id,
                    family=self.family,
                    name="comment_anomaly_score",
                    value=round(composite_comment_anomaly, 4),
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
                    name="comment_repetition_rate",
                    value=round(duplicate_fraction, 4),
                    confidence=0.90,
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
                    name="comment_burst_velocity",
                    value=round(burst_velocity, 4),
                    confidence=0.85,
                    evidence_refs=evidence,
                    producer=self.name,
                    producer_version=self.version,
                )
            )

            if sudden_dormant_activation > 0:
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="temporal_trajectory_anomaly",
                        value=round(sudden_dormant_activation, 4),
                        confidence=0.80,
                        evidence_refs=evidence,
                        producer=self.name,
                        producer_version=self.version,
                    )
                )

        return signals
