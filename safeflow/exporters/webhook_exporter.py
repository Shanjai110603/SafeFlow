"""Signed Webhook Dispatcher for High-Severity SafeFlow Decisions."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
import httpx

from safeflow.core.schema import Decision, RiskLevel


class WebhookDispatcher:
    """Dispatches HTTP POST webhooks with HMAC-SHA256 signatures."""

    def __init__(self, endpoint_url: str, secret_key: str, min_severity: RiskLevel = RiskLevel.HIGH) -> None:
        self.endpoint_url = endpoint_url
        self.secret_key = secret_key
        self.min_severity = min_severity

    def sign_payload(self, payload_bytes: bytes) -> str:
        """Generate HMAC-SHA256 hex signature."""
        return hmac.new(self.secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    def dispatch(self, decision: Decision) -> bool:
        """Send webhook if decision meets or exceeds min_severity threshold."""
        severity_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        if severity_order.get(decision.level, 0) < severity_order.get(self.min_severity, 2):
            return False

        payload_str = decision.model_dump_json()
        payload_bytes = payload_str.encode("utf-8")
        signature = self.sign_payload(payload_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-SafeFlow-Signature": signature,
            "X-SafeFlow-Event": "decision.created",
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(self.endpoint_url, content=payload_bytes, headers=headers)
                return resp.is_success
        except Exception:
            return False
