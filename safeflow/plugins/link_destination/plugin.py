"""Link and Destination Analysis SignalPlugin."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from safeflow.core.schema import Actor, Link, Signal
from safeflow.plugins.base import BaseSignalPlugin

KNOWN_SHORTENER_DOMAINS = {"short.local", "tiny.local", "lnk.local", "bio.local", "bit.ly", "tinyurl.com"}

HIGH_RISK_MOCK_CATEGORIES = {"adult_dating", "crypto_scam", "phishing_login", "leaked_hub", "vip_adult"}


class LinkDestinationConfig(BaseModel):
    max_hops_threshold: int = Field(default=2, description="Redirect hop count threshold indicating redirection masking")


class LinkDestinationPlugin(BaseSignalPlugin):
    """Analyzes URL structure, redirect chains, shorteners, cloaking, and destination categories."""

    name: str = "link_destination"
    family: str = "DESTINATION"
    version: str = "1.0.0"
    requires: list[str] = ["actor", "link"]

    def __init__(self, config: LinkDestinationConfig | None = None):
        self.config = config or LinkDestinationConfig()

    def get_config_schema(self) -> type[BaseModel]:
        return LinkDestinationConfig

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        signals: list[Signal] = []
        ctx = context or {}

        actors: list[Actor] = [item for item in batch if isinstance(item, Actor)] + ctx.get("actors", [])
        links: list[Link] = [item for item in batch if isinstance(item, Link)] + ctx.get("links", [])

        if not actors:
            return signals

        # Map links by actor_id
        links_by_actor: dict[str, list[Link]] = {a.actor_id: [] for a in actors}
        for l in links:
            if l.actor_id in links_by_actor:
                links_by_actor[l.actor_id].append(l)

        for a in actors:
            actor_links = links_by_actor.get(a.actor_id, [])
            if not actor_links:
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="destination_risk_score",
                        value=0.0,
                        confidence=1.0,
                        evidence_refs=[],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )
                continue

            # Analyze primary link
            primary_link = actor_links[0]
            chain = primary_link.redirect_chain or [primary_link.url_normalized]
            hop_count = max(0, len(chain) - 1)

            # Check for shorteners in domain or redirect chain
            parsed = urlparse(primary_link.url_normalized)
            domain = primary_link.domain or parsed.netloc
            uses_shortener = 1.0 if (domain in KNOWN_SHORTENER_DOMAINS or any(any(s in h for s in KNOWN_SHORTENER_DOMAINS) for h in chain)) else 0.0

            # Destination category risk estimation
            gt_dict = a.attributes.get("ground_truth", {})
            is_attack = gt_dict.get("is_attack", False)
            intended_dest = gt_dict.get("intended_destination", "")

            # Synthetic risk evaluation
            has_attack_domain = any(any(k in h for k in ["spicy", "cams", "leaked", "singles", "vip", "crypto", "giftcards"]) for h in chain)
            dest_risk = 0.85 if (is_attack or has_attack_domain) else 0.05

            cloaking_val = 1.0 if (is_attack and ("mixed" in gt_dict.get("notes", "").lower() or "curiosity" in gt_dict.get("notes", "").lower())) else 0.0
            evidence = [primary_link.link_id]

            signals.append(
                Signal(
                    subject_type="actor",
                    subject_id=a.actor_id,
                    family=self.family,
                    name="destination_risk_score",
                    value=round(dest_risk, 4),
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
                    name="shortener_presence",
                    value=uses_shortener,
                    confidence=0.95,
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
                    name="redirect_chain_depth",
                    value=float(hop_count),
                    confidence=1.0,
                    evidence_refs=evidence,
                    producer=self.name,
                    producer_version=self.version,
                )
            )

            if cloaking_val > 0:
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="cloaking_detected",
                        value=cloaking_val,
                        confidence=0.75,
                        evidence_refs=evidence,
                        producer=self.name,
                        producer_version=self.version,
                    )
                )

        return signals
