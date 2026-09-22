"""Actor Profile and Bio Dynamics SignalPlugin."""

from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field
from safeflow.adapters.synthetic.obfuscation import ObfuscationEngine, REVERSE_CONFUSABLE_MAP, ZERO_WIDTH_CHARS
from safeflow.core.schema import Actor, Signal
from safeflow.plugins.base import BaseSignalPlugin

FUNNEL_PROMPT_PATTERNS = [
    r"link\s*in\s*bio",
    r"check\s*(my)?\s*profile",
    r"exclusive\s*(private)?\s*content",
    r"click\s*(the)?\s*link",
    r"my\s*page\s*below",
    r"dm\s*me\s*for",
]


class ActorProfileConfig(BaseModel):
    homoglyph_warning_threshold: float = Field(default=0.15, description="Homoglyph character ratio indicating obfuscation")


class ActorProfilePlugin(BaseSignalPlugin):
    """Analyzes actor profile descriptions for homoglyphs, zero-width spaces, and bio callouts."""

    name: str = "actor_profile"
    family: str = "PROFILE_CHANGE"
    version: str = "1.0.0"
    requires: list[str] = ["actor"]

    def __init__(self, config: ActorProfileConfig | None = None):
        self.config = config or ActorProfileConfig()

    def get_config_schema(self) -> type[BaseModel]:
        return ActorProfileConfig

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        signals: list[Signal] = []
        ctx = context or {}

        actors: list[Actor] = [item for item in batch if isinstance(item, Actor)] + ctx.get("actors", [])

        for a in actors:
            bio_text = a.description_history[-1] if a.description_history else ""
            if not bio_text:
                signals.append(
                    Signal(
                        subject_type="actor",
                        subject_id=a.actor_id,
                        family=self.family,
                        name="homoglyph_density",
                        value=0.0,
                        confidence=1.0,
                        evidence_refs=[],
                        producer=self.name,
                        producer_version=self.version,
                    )
                )
                continue

            # 1. Measure homoglyph and zero-width character density
            confusable_count = sum(1 for ch in bio_text if ch in REVERSE_CONFUSABLE_MAP or ch in ZERO_WIDTH_CHARS)
            total_chars = len(bio_text) or 1
            homoglyph_density = confusable_count / total_chars

            # 2. Bio Link Callout Pattern Matching (on normalized text)
            normalized_bio = ObfuscationEngine.normalize_text(bio_text).lower()
            callout_matches = sum(1 for pat in FUNNEL_PROMPT_PATTERNS if re.search(pat, normalized_bio))
            callout_score = min(1.0, callout_matches * 0.5)

            evidence = [a.actor_id]

            signals.append(
                Signal(
                    subject_type="actor",
                    subject_id=a.actor_id,
                    family=self.family,
                    name="homoglyph_density",
                    value=round(min(1.0, homoglyph_density * 2.0), 4),
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
                    name="bio_link_callout_score",
                    value=round(callout_score, 4),
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
                    name="description_mutation_count",
                    value=float(len(a.description_history)),
                    confidence=1.0,
                    evidence_refs=evidence,
                    producer=self.name,
                    producer_version=self.version,
                )
            )

        return signals
