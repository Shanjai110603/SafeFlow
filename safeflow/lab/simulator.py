"""Interactive Threat Simulation Lab for SafeFlow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
from typing import Sequence

from safeflow.core.schema import Link, LinkSurface, RiskLevel
from safeflow.lab.models import (
    QueueItem,
    ThreatScenarioKind,
    TradeoffPoint,
    TradeoffReport,
)
from safeflow.lab.queue import LinkVerificationQueue


class ThreatSimulationLab:
    """Simulates adversarial threat campaigns and evaluates queue hold-and-verify tradeoffs."""

    @classmethod
    def run_scenario_tradeoff_sweep(
        cls,
        scenario: ThreatScenarioKind | str = ThreatScenarioKind.CURIOSITY_SURGE,
        sample_size: int = 100,
        windows: Sequence[int] = (5, 15, 30, 60, 120),
        seed: int = 42,
    ) -> TradeoffReport:
        """Evaluate tradeoff curves across multiple hold windows for a specific scenario."""
        rng = random.Random(seed)
        scenario_str = scenario.value if isinstance(scenario, ThreatScenarioKind) else str(scenario)
        points: list[TradeoffPoint] = []

        for win in windows:
            queue = LinkVerificationQueue(default_window_minutes=win)
            sim_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            queue.set_time(sim_time)

            # Generate synthetic scenario links
            n_attack = int(sample_size * 0.20)
            n_legit = sample_size - n_attack

            # 1. Enqueue Legit Creators
            for i in range(n_legit):
                link = Link(
                    link_id=f"legit_link_{i}",
                    actor_id=f"legit_actor_{i}",
                    surface=LinkSurface.PROFILE_DESCRIPTION,
                    url_normalized=f"https://portfolio.example{i}.local",
                    domain=f"example{i}.local",
                    redirect_chain=[],
                )
                # 95% of legit creators evaluate to LOW risk; 5% have false positive edge signals
                legit_risk = RiskLevel.LOW if rng.random() > 0.05 else RiskLevel.MEDIUM
                queue.enqueue(
                    link=link,
                    actor_risk=legit_risk,
                    is_attack_ground_truth=False,
                    delayed_activation_hours=0.0,
                    is_cloaked=False,
                )

            # 2. Enqueue Scenario-Specific Attacks
            for i in range(n_attack):
                if scenario_str == ThreatScenarioKind.CLOAKED_REDIRECT_EVASION.value:
                    delayed_act = rng.choice([0.5, 1.0, 2.0])  # 30m, 60m, 120m delay
                    is_cloaked = rng.random() < 0.20
                    attack_risk = RiskLevel.HIGH if rng.random() < 0.85 else RiskLevel.MEDIUM
                elif scenario_str == ThreatScenarioKind.DORMANT_HIJACK_BURST.value:
                    delayed_act = 0.0
                    is_cloaked = False
                    attack_risk = RiskLevel.CRITICAL if rng.random() < 0.90 else RiskLevel.HIGH
                else:  # CURIOSITY_SURGE or AVATAR_MUTATION_RING
                    delayed_act = rng.choice([0.0, 0.25, 0.5])  # 0m, 15m, 30m delay
                    is_cloaked = False
                    attack_risk = RiskLevel.HIGH if rng.random() < 0.90 else RiskLevel.MEDIUM

                link = Link(
                    link_id=f"attack_link_{i}",
                    actor_id=f"attack_actor_{i}",
                    surface=LinkSurface.PROFILE_DESCRIPTION,
                    url_normalized=f"https://promo-hop.dating{i}.local",
                    domain=f"dating{i}.local",
                    redirect_chain=[f"dating{i}.local", f"target-funnel{i}.local"],
                )
                queue.enqueue(
                    link=link,
                    actor_risk=attack_risk,
                    is_attack_ground_truth=True,
                    delayed_activation_hours=delayed_act,
                    is_cloaked=is_cloaked,
                )

            # Advance clock incrementally in 5-minute ticks up to 240 minutes (4 hours)
            for _ in range(48):
                queue.advance_clock(delta_minutes=5)

            point = queue.compute_tradeoff_point(window_minutes=win)
            points.append(point)

        # Select optimal window (highest AIR with CDR < 0.10)
        best_win = 30
        for p in points:
            if p.attack_interception_rate >= 0.85 and p.creator_delay_rate <= 0.10:
                best_win = p.window_minutes
                break

        rec = (
            f"Recommended window for scenario '{scenario_str}': {best_win} minutes "
            f"(AIR: {next((p.attack_interception_rate for p in points if p.window_minutes == best_win), 0.0):.2%}, "
            f"Creator Friction: {next((p.creator_delay_rate for p in points if p.window_minutes == best_win), 0.0):.2%})"
        )

        return TradeoffReport(
            scenario=scenario_str,
            points=points,
            optimal_window_minutes=best_win,
            recommendation=rec,
        )
