"""Tests for SafeFlow Milestone 7 Threat Simulation Lab & Link Verification Queue.

Validates:
1. Low-risk legitimate creator links release immediately with zero delay.
2. High/critical risk links are queued and re-scanned upon virtual clock advancement.
3. Delayed activation attacks are intercepted before appearing on public feeds.
4. Tradeoff curve sweeps across 5m, 15m, 30m, 60m, and 120m review windows.
"""

from datetime import datetime, timezone
import pytest

from safeflow.core.schema import Link, LinkSurface, RiskLevel
from safeflow.lab.models import (
    QueueItemStatus,
    ThreatScenarioKind,
    TradeoffReport,
)
from safeflow.lab.queue import LinkVerificationQueue
from safeflow.lab.simulator import ThreatSimulationLab


def test_link_verification_queue_immediate_release_for_low_risk():
    queue = LinkVerificationQueue(default_window_minutes=30)
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    queue.set_time(now)

    link = Link(
        link_id="legit_1",
        actor_id="actor_legit",
        surface=LinkSurface.PROFILE_DESCRIPTION,
        url_normalized="https://myart.local",
        domain="myart.local",
        redirect_chain=[],
    )

    item = queue.enqueue(link=link, actor_risk=RiskLevel.LOW)
    assert item.status == QueueItemStatus.RELEASED
    assert item.release_at == now
    assert (item.release_at - item.submitted_at).total_seconds() == 0.0


def test_link_verification_queue_catches_delayed_activation():
    queue = LinkVerificationQueue(default_window_minutes=60)
    start_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    queue.set_time(start_time)

    # Attack link with 45-minute delayed activation
    attack_link = Link(
        link_id="attack_delayed_1",
        actor_id="actor_attacker",
        surface=LinkSurface.PROFILE_DESCRIPTION,
        url_normalized="https://delayed-hop.dating.local",
        domain="dating.local",
        redirect_chain=["dating.local", "target-funnel.local"],
    )

    item = queue.enqueue(
        link=attack_link,
        actor_risk=RiskLevel.HIGH,
        is_attack_ground_truth=True,
        delayed_activation_hours=0.75,  # 45 minutes
        is_cloaked=False,
    )
    assert item.status == QueueItemStatus.PENDING

    # Advance clock by 30 minutes (before activation)
    res_30 = queue.advance_clock(delta_minutes=30)
    assert item.status == QueueItemStatus.PENDING
    assert len(res_30["blocked"]) == 0

    # Advance clock by another 20 minutes (total 50 minutes, past 45m activation)
    res_50 = queue.advance_clock(delta_minutes=20)
    assert item.status == QueueItemStatus.BLOCKED
    assert len(res_50["blocked"]) == 1
    assert "malicious destination hop" in item.reasons[0]


@pytest.mark.parametrize(
    "scenario",
    [
        ThreatScenarioKind.CURIOSITY_SURGE,
        ThreatScenarioKind.CLOAKED_REDIRECT_EVASION,
        ThreatScenarioKind.DORMANT_HIJACK_BURST,
    ],
)
def test_threat_simulation_lab_tradeoff_sweep(scenario: ThreatScenarioKind):
    report = ThreatSimulationLab.run_scenario_tradeoff_sweep(
        scenario=scenario,
        sample_size=60,
        windows=[5, 15, 30, 60, 120],
    )
    assert isinstance(report, TradeoffReport)
    assert len(report.points) == 5
    assert report.optimal_window_minutes in [5, 15, 30, 60, 120]

    # Verify that longer windows generally increase delayed activation interception
    p_5 = report.points[0]
    p_120 = report.points[-1]
    assert p_120.delayed_activation_interception_rate >= p_5.delayed_activation_interception_rate
    # Legit creator delay rate should remain low (< 0.15)
    for p in report.points:
        assert p.creator_delay_rate <= 0.15
