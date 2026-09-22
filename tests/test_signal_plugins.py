"""Unit and integration tests for SafeFlow SignalPlugins suite (Milestone 3)."""

from __future__ import annotations

import pytest
from safeflow.adapters.synthetic.generator import GeneratorConfig, SyntheticGenerator
from safeflow.core.registry import PluginRegistry, SignalPlugin
from safeflow.plugins.actor_profile.plugin import ActorProfilePlugin
from safeflow.plugins.link_destination.plugin import LinkDestinationPlugin
from safeflow.plugins.media_reuse.plugin import MediaReusePlugin
from safeflow.plugins.targeting.plugin import TargetingPlugin
from safeflow.plugins.text_behavior.plugin import TextBehaviorPlugin


@pytest.fixture
def sample_dataset():
    cfg = GeneratorConfig(seed=42, variant="A", platform_profile="video_comments", actor_count=150)
    return SyntheticGenerator(cfg).generate()


def test_all_plugins_conform_to_protocol_and_register():
    """Verify that all signal plugins implement SignalPlugin protocol and register cleanly."""
    registry = PluginRegistry()
    plugins = [
        MediaReusePlugin(),
        TextBehaviorPlugin(),
        TargetingPlugin(),
        LinkDestinationPlugin(),
        ActorProfilePlugin(),
    ]

    for p in plugins:
        assert isinstance(p, SignalPlugin)
        registry.register(p)
        assert registry.get(p.name) is p
        assert p.family in ("IMAGE_LINK", "BEHAVIOR", "TARGETING", "DESTINATION", "PROFILE_CHANGE")


def test_curiosity_funnel_has_low_comment_anomaly(sample_dataset):
    """Assert: A normal comment in a curiosity funnel account yields a low comment anomaly score."""
    plugin = TextBehaviorPlugin()
    funnel_actors = [
        a for a in sample_dataset.actors
        if a.attributes.get("ground_truth", {}).get("category") == "CURIOSITY_FUNNEL"
    ]
    assert len(funnel_actors) > 0

    signals = plugin.run(batch=sample_dataset.actors, context={"content": sample_dataset.content})
    funnel_actor_ids = {a.actor_id for a in funnel_actors}

    anomaly_signals = [
        s for s in signals
        if s.subject_id in funnel_actor_ids and s.name == "comment_anomaly_score"
    ]
    assert len(anomaly_signals) > 0
    # Because curiosity funnel comments are normal/benign, comment anomaly score should be low (< 0.50)
    for s in anomaly_signals:
        assert s.value < 0.50, f"Curiosity funnel comment anomaly unexpectedly high: {s.value}"


def test_legit_avatar_reuse_is_discounted(sample_dataset):
    """Assert: Legit avatar reuse yields a discounted reuse signal via popularity discounting."""
    plugin = MediaReusePlugin()
    legit_reuse_actors = [
        a for a in sample_dataset.actors
        if a.attributes.get("ground_truth", {}).get("category") == "LEGIT_AVATAR_REUSE"
    ]
    assert len(legit_reuse_actors) > 0
    legit_reuse_ids = {a.actor_id for a in legit_reuse_actors}

    signals = plugin.run(batch=sample_dataset.actors, context={"media": sample_dataset.media})

    reuse_score_signals = [
        s for s in signals
        if s.subject_id in legit_reuse_ids and s.name == "media_reuse_score"
    ]
    assert len(reuse_score_signals) > 0
    # Popularity discounting attenuates large clusters so reuse score remains low (< 0.40)
    for s in reuse_score_signals:
        assert s.value < 0.40, f"Legit avatar reuse score was not properly discounted: {s.value}"


def test_targeting_signal_does_not_fire_on_normal_high_engagement(sample_dataset):
    """Assert: The targeting signal does not fire excessively on NORMAL_HIGH_ENGAGEMENT users."""
    plugin = TargetingPlugin()
    high_eng_actors = [
        a for a in sample_dataset.actors
        if a.attributes.get("ground_truth", {}).get("category") == "NORMAL_HIGH_ENGAGEMENT"
    ]
    assert len(high_eng_actors) > 0
    high_eng_ids = {a.actor_id for a in high_eng_actors}

    signals = plugin.run(
        batch=sample_dataset.actors,
        context={"content": sample_dataset.content, "spaces": sample_dataset.spaces}
    )

    risk_ratio_signals = [
        s for s in signals
        if s.subject_id in high_eng_ids and s.name == "targeting_risk_ratio"
    ]
    assert len(risk_ratio_signals) > 0
    for s in risk_ratio_signals:
        assert s.value < 0.50, f"Targeting risk ratio unexpectedly high for organic high engagement user: {s.value}"


@pytest.mark.parametrize("profile", ["video_comments", "forum_communities", "chat_servers"])
@pytest.mark.parametrize("variant", ["A", "B"])
def test_feature_matrices_build_on_all_profiles_and_variants(profile: str, variant: str):
    """Assert: Feature signals run end-to-end across all 3 platform profiles and both variants."""
    cfg = GeneratorConfig(seed=202, variant=variant, platform_profile=profile, actor_count=80)  # type: ignore[arg-type]
    ds = SyntheticGenerator(cfg).generate()

    plugins = [
        MediaReusePlugin(),
        TextBehaviorPlugin(),
        TargetingPlugin(),
        LinkDestinationPlugin(),
        ActorProfilePlugin(),
    ]

    all_signals = []
    ctx = {
        "actors": ds.actors,
        "content": ds.content,
        "media": ds.media,
        "spaces": ds.spaces,
        "links": ds.links,
    }

    for p in plugins:
        res = p.run(batch=ds.actors, context=ctx)
        all_signals.extend(res)

    assert len(all_signals) > 0
    # Every actor should have received signals from multiple families
    actor_families: dict[str, set[str]] = {}
    for s in all_signals:
        if s.subject_type == "actor":
            actor_families.setdefault(s.subject_id, set()).add(s.family)

    for a in ds.actors:
        assert len(actor_families.get(a.actor_id, set())) >= 3, f"Actor {a.actor_id} received insufficient signal families"
