"""Risk-adaptive simulated-clock Link Verification Queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence
import uuid

from safeflow.core.schema import Link, RiskLevel
from safeflow.lab.models import QueueItem, QueueItemStatus, TradeoffPoint


class LinkVerificationQueue:
    """Risk-adaptive hold-and-verify queue for external URLs driven by a simulated clock."""

    def __init__(self, default_window_minutes: int = 30) -> None:
        self.default_window_minutes = default_window_minutes
        self.current_time = datetime.now(timezone.utc)
        self.items: list[QueueItem] = []

    def __len__(self) -> int:
        """Return total number of items in the queue."""
        return len(self.items)

    def set_time(self, new_time: datetime) -> None:
        """Set simulated clock to an exact timestamp."""
        self.current_time = new_time

    def enqueue(
        self,
        link: Link,
        actor_risk: RiskLevel,
        is_attack_ground_truth: bool = False,
        delayed_activation_hours: float = 0.0,
        is_cloaked: bool = False,
        reasons: list[str] | None = None,
    ) -> QueueItem:
        """Submit a link to the queue. Low risk links release immediately with 0 delay."""
        item_id = f"queue_{uuid.uuid4().hex[:12]}"

        # Calculate hold window according to risk tier
        if actor_risk == RiskLevel.LOW:
            hold_minutes = 0
            status = QueueItemStatus.RELEASED
        elif actor_risk == RiskLevel.MEDIUM:
            hold_minutes = max(5, self.default_window_minutes // 2)
            status = QueueItemStatus.PENDING
        elif actor_risk == RiskLevel.HIGH:
            hold_minutes = self.default_window_minutes
            status = QueueItemStatus.PENDING
        else:  # CRITICAL
            hold_minutes = self.default_window_minutes * 2
            status = QueueItemStatus.PENDING

        release_at = self.current_time + timedelta(minutes=hold_minutes)

        item = QueueItem(
            item_id=item_id,
            link_id=link.link_id,
            actor_id=link.actor_id,
            url=link.url_normalized,
            domain=link.domain,
            submitted_at=self.current_time,
            release_at=release_at,
            status=status,
            actor_risk=actor_risk,
            is_attack_ground_truth=is_attack_ground_truth,
            delayed_activation_hours=delayed_activation_hours,
            is_cloaked=is_cloaked,
            reasons=reasons or [],
        )
        self.items.append(item)
        return item

    def advance_clock(self, delta_minutes: int) -> dict[str, list[QueueItem]]:
        """Advance simulated clock by delta_minutes and evaluate pending queue items."""
        self.current_time += timedelta(minutes=delta_minutes)
        newly_released: list[QueueItem] = []
        newly_blocked: list[QueueItem] = []

        for item in self.items:
            if item.status != QueueItemStatus.PENDING:
                continue

            elapsed_hours = (self.current_time - item.submitted_at).total_seconds() / 3600.0

            # Dynamic re-scan evaluation
            if item.is_attack_ground_truth:
                # If delayed activation period has elapsed, the malicious redirect is uncovered
                if elapsed_hours >= item.delayed_activation_hours:
                    item.status = QueueItemStatus.BLOCKED
                    item.reasons.append(
                        f"Dynamic rescan detected malicious destination hop after {elapsed_hours:.2f}h"
                    )
                    newly_blocked.append(item)
                    continue

            # Check if hold window has expired cleanly
            if self.current_time >= item.release_at:
                if item.is_attack_ground_truth and item.is_cloaked:
                    # Cloaking evasion bypassed the hold window
                    item.status = QueueItemStatus.RELEASED
                    item.reasons.append("Released upon hold window expiry (cloaking bypass)")
                    newly_released.append(item)
                elif item.is_attack_ground_truth:
                    # Delayed activation did not trigger before release
                    item.status = QueueItemStatus.RELEASED
                    item.reasons.append("Released upon hold window expiry (delayed activation bypass)")
                    newly_released.append(item)
                else:
                    item.status = QueueItemStatus.RELEASED
                    newly_released.append(item)

        return {
            "released": newly_released,
            "blocked": newly_blocked,
        }

    def compute_tradeoff_point(self, window_minutes: int) -> TradeoffPoint:
        """Compute tradeoff metrics for the current queue state."""
        total_malicious = sum(1 for i in self.items if i.is_attack_ground_truth)
        total_legit = sum(1 for i in self.items if not i.is_attack_ground_truth)

        blocked_malicious = sum(
            1 for i in self.items if i.is_attack_ground_truth and i.status == QueueItemStatus.BLOCKED
        )
        delayed_legit = sum(
            1 for i in self.items
            if not i.is_attack_ground_truth and i.actor_risk != RiskLevel.LOW
        )

        delayed_malicious_total = sum(
            1 for i in self.items if i.is_attack_ground_truth and i.delayed_activation_hours > 0.0
        )
        delayed_malicious_caught = sum(
            1 for i in self.items
            if i.is_attack_ground_truth and i.delayed_activation_hours > 0.0 and i.status == QueueItemStatus.BLOCKED
        )

        air = (blocked_malicious / total_malicious) if total_malicious > 0 else 1.0
        cdr = (delayed_legit / total_legit) if total_legit > 0 else 0.0
        dair = (delayed_malicious_caught / delayed_malicious_total) if delayed_malicious_total > 0 else 1.0

        legit_holds = [
            (i.release_at - i.submitted_at).total_seconds()
            for i in self.items if not i.is_attack_ground_truth
        ]
        mean_hold = float(sum(legit_holds) / len(legit_holds)) if legit_holds else 0.0

        return TradeoffPoint(
            window_minutes=window_minutes,
            attack_interception_rate=round(air, 4),
            creator_delay_rate=round(cdr, 4),
            delayed_activation_interception_rate=round(dair, 4),
            mean_hold_seconds_legit=round(mean_hold, 1),
        )
