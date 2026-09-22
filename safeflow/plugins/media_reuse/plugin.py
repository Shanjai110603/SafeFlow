"""Media Reuse and Avatar Linking SignalPlugin."""

from __future__ import annotations

import math
from typing import Any
from pydantic import BaseModel, Field
from safeflow.core.schema import Actor, Media, Signal
from safeflow.plugins.base import BaseSignalPlugin


def _hamming_distance(h1: str, h2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if len(h1) != len(h2):
        return 64
    try:
        val1 = int(h1, 16)
        val2 = int(h2, 16)
        return bin(val1 ^ val2).count("1")
    except ValueError:
        return 64


class MediaReuseConfig(BaseModel):
    max_hamming_distance: int = Field(default=8, description="Max Hamming distance for perceptual hash clustering")
    popularity_discount_threshold: float = Field(default=0.05, description="Prevalence above which reuse is discounted as a meme/default")
    max_ai_likelihood_signal: float = Field(default=0.45, description="Upper cap on weak AI likelihood signal")


class MediaReusePlugin(BaseSignalPlugin):
    """Detects media reuse, perceptual hash clustering with popularity discounting, and AI identity cues."""

    name: str = "media_reuse"
    family: str = "IMAGE_LINK"
    version: str = "1.0.0"
    requires: list[str] = ["actor", "media"]

    def __init__(self, config: MediaReuseConfig | None = None):
        self.config = config or MediaReuseConfig()

    def get_config_schema(self) -> type[BaseModel]:
        return MediaReuseConfig

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        signals: list[Signal] = []
        ctx = context or {}

        actors: list[Actor] = [item for item in batch if isinstance(item, Actor)] + ctx.get("actors", [])
        media_items: list[Media] = [item for item in batch if isinstance(item, Media)] + ctx.get("media", [])

        if not actors:
            return signals

        # Map media by media_id
        media_by_id = {m.media_id: m for m in media_items}
        total_actors = len(actors)

        # 1. Cluster avatars by perceptual hash (pHash / dHash)
        # Map actor to primary hash
        actor_hashes: dict[str, tuple[str, str, Media | None]] = {}
        for a in actors:
            m = media_by_id.get(a.avatar_media_id) if a.avatar_media_id else None
            ph = m.perceptual_hashes.get("phash", "") if m else ""
            dh = m.perceptual_hashes.get("dhash", "") if m else ""
            actor_hashes[a.actor_id] = (ph, dh, m)

        # Count cluster frequencies with Hamming thresholding
        hash_clusters: list[list[str]] = []
        visited: set[str] = set()

        actor_ids = list(actor_hashes.keys())
        for i, a1_id in enumerate(actor_ids):
            if a1_id in visited:
                continue
            ph1, dh1, _ = actor_hashes[a1_id]
            if not ph1:
                continue
            cluster = [a1_id]
            visited.add(a1_id)

            for a2_id in actor_ids[i + 1:]:
                if a2_id in visited:
                    continue
                ph2, dh2, _ = actor_hashes[a2_id]
                if not ph2:
                    continue

                # Check pHash and dHash proximity
                dist_p = _hamming_distance(ph1, ph2)
                dist_d = _hamming_distance(dh1, dh2)
                if dist_p <= self.config.max_hamming_distance or dist_d <= 4:
                    cluster.append(a2_id)
                    visited.add(a2_id)

            if len(cluster) > 1:
                hash_clusters.append(cluster)

        # Map actor to cluster size
        actor_cluster_size: dict[str, tuple[int, list[str]]] = {}
        for cluster in hash_clusters:
            for a_id in cluster:
                actor_cluster_size[a_id] = (len(cluster), cluster)

        # 2. Compute Popularity-Discounted Signals per Actor
        for a in actors:
            ph, dh, m = actor_hashes.get(a.actor_id, ("", "", None))
            cluster_info = actor_cluster_size.get(a.actor_id)

            if cluster_info:
                cluster_len, cluster_peers = cluster_info
                # Popularity discounting (IDF-style)
                prevalence = cluster_len / max(1, total_actors)
                if prevalence > self.config.popularity_discount_threshold:
                    # Discount heavily for viral meme / default avatar saturation
                    excess = prevalence - self.config.popularity_discount_threshold
                    idf_discount = max(0.05, 1.0 - excess * 6.5)
                else:
                    # Full weight for tight coordinated rings
                    idf_discount = 1.0

                # Normalized reuse score between 0.0 and 1.0
                raw_reuse_factor = min(1.0, (cluster_len - 1) / 10.0)
                discounted_score = min(1.0, raw_reuse_factor * idf_discount)

                peer_refs = [p for p in cluster_peers if p != a.actor_id][:5]
                evidence = [a.avatar_media_id] if a.avatar_media_id else []
                evidence.extend(peer_refs)

                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="media_reuse_score",
                        value=round(discounted_score, 4),
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
                        name="media_reuse_count",
                        value=float(cluster_len),
                        confidence=1.0,
                        evidence_refs=evidence,
                        producer=self.name,
                        producer_version=self.version,
                    )
                )
            else:
                # Zero reuse
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="media_reuse_score",
                        value=0.0,
                        confidence=1.0,
                        evidence_refs=[a.avatar_media_id] if a.avatar_media_id else [],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )

            # 3. Weak AI Likelihood Signal
            ai_lik = float(a.attributes.get("ai_likelihood", 0.05))
            if ai_lik > 0.5:
                # Weak signal, capped
                capped_ai_score = min(self.config.max_ai_likelihood_signal, ai_lik * 0.45)
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="ai_generated_identity_score",
                        value=round(capped_ai_score, 4),
                        confidence=0.60,
                        evidence_refs=[a.avatar_media_id] if a.avatar_media_id else [],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )

            # 4. Gate-derived tag signal
            if m and any(t.name == "suggestive_presentation" for t in m.tags):
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="suggestive_presentation_flag",
                        value=0.50,  # Weak baseline flag
                        confidence=0.90,
                        evidence_refs=[m.media_id],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )

        return signals
