"""Structured explanation generator for SafeFlow Decision Engine.

Generates analyst-facing evidence and counter-evidence lists explaining why an entity
was flagged or why certain signals were mitigated/discounted.
"""

from __future__ import annotations

from typing import Sequence
from safeflow.core.schema import Signal


class DecisionExplainer:
    """Generates explainable evidence and counter-evidence descriptions."""

    @classmethod
    def generate_explanation(
        cls,
        signals: Sequence[Signal],
        gating_reasons: Sequence[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Generate structured evidence and counter-evidence points.
        
        Returns:
            (evidence_list, counter_evidence_list)
        """
        evidence: list[str] = []
        counter_evidence: list[str] = []

        # Analyze individual signals
        for s in signals:
            # Evidence (elevated risk)
            if s.value >= 0.50:
                if s.name == "media_max_reuse":
                    evidence.append(f"High media reuse ({s.value:.2f}) across actor network")
                elif s.name in ("media_suggestive_score", "suggestive_presentation"):
                    evidence.append(f"Elevated suggestive presentation score ({s.value:.2f})")
                elif s.name in ("media_ai_likelihood", "ai_likelihood"):
                    evidence.append(f"Elevated AI-generated identity probability ({s.value:.2f})")
                elif s.name == "text_repetition_rate":
                    evidence.append(f"High text template repetition rate ({s.value:.2f})")
                elif s.name == "text_burst_velocity":
                    evidence.append(f"Abnormal temporal burst velocity ({s.value:.2f})")
                elif s.name == "text_dormancy_anomaly":
                    evidence.append(f"Sudden activity burst following dormancy ({s.value:.2f})")
                elif s.name == "targeting_percentile_conc":
                    evidence.append(f"Concentrated targeting of high-popularity spaces ({s.value:.2f})")
                elif s.name == "targeting_bipartite_risk":
                    evidence.append(f"High bipartite co-targeting risk ratio ({s.value:.2f})")
                elif s.name in ("link_max_dest_risk", "link_destination_risk"):
                    evidence.append(f"High-risk destination domain detected ({s.value:.2f})")
                elif s.name == "link_is_cloaked":
                    evidence.append("Cloaked or evasive redirect chain identified")
                elif s.name == "link_uses_shortener":
                    evidence.append("URL shortener obfuscation in use")
                elif s.name == "profile_homoglyph_density":
                    evidence.append(f"Elevated homoglyph/zero-width character density ({s.value:.2f})")
                elif s.name == "profile_bio_callout_score":
                    evidence.append(f"Bio callout pattern encouraging off-platform redirection ({s.value:.2f})")
                else:
                    evidence.append(f"Signal {s.family}:{s.name} triggered ({s.value:.2f})")

            # Counter-evidence (benign / mitigating signals)
            elif s.value <= 0.20:
                if s.name == "text_repetition_rate":
                    counter_evidence.append("High lexical diversity across content (low repetition)")
                elif s.name == "media_max_reuse":
                    counter_evidence.append("Unique profile imagery (zero suspicious reuse detected)")
                elif s.name == "targeting_bipartite_risk":
                    counter_evidence.append("Normal audience space distribution consistent with organic activity")
                elif s.name in ("link_max_dest_risk", "link_destination_risk"):
                    counter_evidence.append("Zero abusive or malicious destination URLs identified")
                elif s.name == "profile_bio_callout_score":
                    counter_evidence.append("No off-platform redirect keywords or funnel patterns in profile")

        # Check for popularity discounting
        for s in signals:
            if s.name == "media_max_reuse" and 0.0 < s.value < 0.45:
                counter_evidence.append(
                    "Avatar reuse discounted: High community prevalence indicates viral meme or default avatar"
                )

        # Append any gating reasons to counter-evidence
        if gating_reasons:
            for reason in gating_reasons:
                counter_evidence.append(f"Safety Gate: {reason}")

        if not evidence:
            evidence.append("All observed signals within normal baseline thresholds")

        if not counter_evidence:
            counter_evidence.append("No mitigating counter-evidence identified across evaluated signals")

        return evidence, counter_evidence
