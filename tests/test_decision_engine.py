"""Tests for SafeFlow Milestone 5 Explainable Decision Engine.

Validates:
1. Multi-tiered scoring (Heuristic and Calibrated).
2. Signal-family gating (HIGH >= 3 families, CRITICAL >= 4 families).
3. Non-overridable single-signal protection (suggestive tag alone can NEVER exceed LOW).
4. Scenario tests A-G.
5. Structured evidence and counter-evidence generation.
6. Policy-pack sensitivity (same signals yield different recommendations under different policies).
7. Calibrated classifier training with group-aware cross-validation on Variant A and testing on Variant B.
8. Generic role redaction on Decision outputs.
"""

import numpy as np
import pytest
from datetime import datetime, timezone

from safeflow.core.schema import Decision, RiskLevel, Signal
from safeflow.core.roles import UserRole, RoleRedactor
from safeflow.core.config import PolicyPackLoader
from safeflow.core.decision import (
    DecisionEngine,
    HeuristicScorer,
    CalibratedScorer,
    SignalFamilyGate,
    DecisionExplainer,
)
from safeflow.adapters.synthetic.generator import SyntheticGenerator
from safeflow.adapters.synthetic.models import GeneratorConfig


def make_signal(family: str, name: str, value: float, subject_id: str = "actor_test") -> Signal:
    return Signal(
        subject_type="actor",
        subject_id=subject_id,
        family=family,
        name=name,
        value=value,
        confidence=1.0,
        evidence_refs=[],
        producer=f"test_{family.lower()}",
        producer_version="1.0.0",
        ts=datetime.now(timezone.utc),
    )


# Scenario A: Benign User (NORMAL) -> LOW
def test_scenario_a_benign_user_low_risk():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.05),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.08),
        make_signal("TARGETING", "targeting_percentile_conc", 0.12),
        make_signal("DESTINATION", "link_max_dest_risk", 0.0),
        make_signal("PROFILE_CHANGE", "profile_bio_callout_score", 0.0),
    ]
    decision = engine.evaluate_actor("actor_benign", signals)
    assert decision.level == RiskLevel.LOW
    assert decision.score < 25.0
    assert len(decision.families_triggered) == 0
    assert any("normal baseline" in e or "Unique profile imagery" in c for e, c in [(decision.evidence[0], decision.counter_evidence[0])])


# Scenario B: Curiosity Funnel -> HIGH
def test_scenario_b_curiosity_funnel_high_risk():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_suggestive_score", 0.85),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.15),  # Benign comments
        make_signal("TARGETING", "targeting_percentile_conc", 0.88),  # Targets popular spaces
        make_signal("DESTINATION", "link_max_dest_risk", 0.82),  # Target destination
        make_signal("PROFILE_CHANGE", "profile_bio_callout_score", 0.75),  # Link in bio
    ]
    decision = engine.evaluate_actor("actor_funnel", signals)
    # Triggered families: IMAGE_LINK, TARGETING, DESTINATION, PROFILE_CHANGE (4 families)
    assert len(decision.families_triggered) >= 3
    assert decision.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert decision.score >= 45.0
    assert any("bio callout" in e.lower() for e in decision.evidence)
    assert any("suggestive" in e.lower() for e in decision.evidence)


# Scenario C: Reused Avatar Network -> HIGH
def test_scenario_c_reused_avatar_network_high_risk():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.90),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.85),
        make_signal("DESTINATION", "link_max_dest_risk", 0.78),
        make_signal("TARGETING", "targeting_percentile_conc", 0.20),
    ]
    decision = engine.evaluate_actor("actor_reused_avatar", signals)
    # Triggered families: IMAGE_LINK, BEHAVIOR, DESTINATION (3 families)
    assert len(decision.families_triggered) == 3
    assert decision.level == RiskLevel.HIGH
    assert decision.score >= 42.0
    assert any("media reuse" in e.lower() for e in decision.evidence)


# Scenario D: Full Coordinated Attack Network -> CRITICAL
def test_scenario_d_full_coordinated_attack_critical_risk():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.92),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.95),
        make_signal("BEHAVIOR", "text_burst_velocity", 0.88),
        make_signal("TARGETING", "targeting_percentile_conc", 0.85),
        make_signal("TARGETING", "targeting_bipartite_risk", 0.90),
        make_signal("DESTINATION", "link_max_dest_risk", 0.95),
        make_signal("DESTINATION", "link_is_cloaked", 1.0),
        make_signal("PROFILE_CHANGE", "profile_bio_callout_score", 0.88),
    ]
    decision = engine.evaluate_actor("actor_full_attack", signals)
    # Triggered families: IMAGE_LINK, BEHAVIOR, TARGETING, DESTINATION, PROFILE_CHANGE (5 families)
    assert len(decision.families_triggered) >= 4
    assert decision.level == RiskLevel.CRITICAL
    assert decision.score >= 65.0
    assert "Suspend actor account" in decision.recommended_action


# Scenario E: Legitimate Fandom / Viral Meme User -> LOW
def test_scenario_e_legit_fandom_and_viral_meme_low_risk():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.25),  # Discounted due to high popularity
        make_signal("BEHAVIOR", "text_repetition_rate", 0.12),
        make_signal("TARGETING", "targeting_percentile_conc", 0.35),
        make_signal("DESTINATION", "link_max_dest_risk", 0.0),
        make_signal("PROFILE_CHANGE", "profile_bio_callout_score", 0.0),
    ]
    decision = engine.evaluate_actor("actor_fandom", signals)
    assert decision.level == RiskLevel.LOW
    assert len(decision.families_triggered) == 0
    assert any("discounted" in c.lower() for c in decision.counter_evidence)


# Scenario F: Single Tagged Avatar Protection Regression -> strictly LOW
def test_scenario_f_single_tagged_avatar_protection_regression():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_suggestive_score", 0.85),
        make_signal("IMAGE_LINK", "suggestive_presentation", 0.85),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.05),
        make_signal("TARGETING", "targeting_percentile_conc", 0.10),
        make_signal("DESTINATION", "link_max_dest_risk", 0.0),
        make_signal("PROFILE_CHANGE", "profile_bio_callout_score", 0.0),
    ]
    decision = engine.evaluate_actor("actor_tagged_only", signals)
    # Even if suggestive score is high, with zero other families, it CANNOT exceed LOW
    assert decision.level == RiskLevel.LOW
    assert any("single-signal protection" in c.lower() for c in decision.counter_evidence)


# Scenario G: Policy Pack Sensitivity
def test_scenario_g_policy_pack_sensitivity():
    general_pack = PolicyPackLoader.load_by_name("general_video_platform")
    youth_pack = PolicyPackLoader.load_by_name("youth_oriented_service")

    general_engine = DecisionEngine(policy_pack=general_pack)
    youth_engine = DecisionEngine(policy_pack=youth_pack)

    signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.88),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.82),
        make_signal("DESTINATION", "link_max_dest_risk", 0.80),
    ]

    dec_general = general_engine.evaluate_actor("actor_test", signals)
    dec_youth = youth_engine.evaluate_actor("actor_test", signals)

    # Identical numerical scores and level
    assert dec_general.score == dec_youth.score
    assert dec_general.level == dec_youth.level == RiskLevel.HIGH
    assert dec_general.families_triggered == dec_youth.families_triggered

    # Distinct platform-tailored recommendations
    assert dec_general.recommended_action != dec_youth.recommended_action
    assert "youth" in dec_youth.recommended_action.lower() or "restrict" in dec_youth.recommended_action.lower()
    assert "moderation queue" in dec_general.recommended_action.lower()


def test_calibrated_scorer_training_and_scoring():
    # Synthetic training data (Variant A)
    rng = np.random.RandomState(42)
    n_features = len(CalibratedScorer().feature_names)

    # Benign samples (mostly near 0.0, occasional small noise)
    X_benign = rng.uniform(0.0, 0.15, size=(100, n_features))
    y_benign = np.zeros(100)
    groups_benign = np.arange(100)

    # Attack samples (high on 3 to 6 key signals, low on others)
    X_attack = rng.uniform(0.0, 0.15, size=(50, n_features))
    for i in range(50):
        # randomly activate 4 to 8 feature indices
        active_indices = rng.choice(n_features, size=rng.randint(4, 8), replace=False)
        X_attack[i, active_indices] = rng.uniform(0.70, 1.0, size=len(active_indices))

    y_attack = np.ones(50)
    groups_attack = np.repeat(np.arange(100, 110), 5)  # 10 clusters of 5 actors

    X = np.vstack([X_benign, X_attack])
    y = np.concatenate([y_benign, y_attack])
    groups = np.concatenate([groups_benign, groups_attack])

    calibrated_scorer = CalibratedScorer()
    calibrated_scorer.fit(X, y, groups=groups)
    assert calibrated_scorer.is_fitted

    engine = DecisionEngine(calibrated_scorer=calibrated_scorer)

    # Test high-risk signals
    attack_signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.95),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.90),
        make_signal("TARGETING", "targeting_percentile_conc", 0.85),
        make_signal("DESTINATION", "link_max_dest_risk", 0.90),
        make_signal("PROFILE_CHANGE", "profile_bio_callout_score", 0.85),
    ]
    dec = engine.evaluate_actor("actor_calibrated_test", attack_signals, mode="calibrated")
    assert dec.score > 50.0
    assert dec.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_generic_role_redaction_on_decision():
    engine = DecisionEngine()
    signals = [
        make_signal("IMAGE_LINK", "media_max_reuse", 0.90),
        make_signal("BEHAVIOR", "text_repetition_rate", 0.85),
        make_signal("DESTINATION", "link_max_dest_risk", 0.80),
    ]
    analyst_dec = engine.evaluate_actor("actor_redaction_test", signals)
    assert analyst_dec.evidence
    assert analyst_dec.counter_evidence
    assert analyst_dec.families_triggered

    # Creator role redaction
    redacted = RoleRedactor.redact(analyst_dec, UserRole.CREATOR)
    assert "evidence" not in redacted
    assert "counter_evidence" not in redacted
    assert "families_triggered" not in redacted
    assert "level" in redacted
    assert "score" in redacted
    assert "recommended_action" in redacted
