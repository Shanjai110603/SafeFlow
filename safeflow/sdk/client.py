"""Lightweight Python SDK client for SafeFlow API."""

from __future__ import annotations

import base64
from typing import Any, Sequence
import httpx

from safeflow.core.schema import Decision, RiskLevel, Signal


class SafeFlowClient:
    """Synchronous and asynchronous client for interacting with SafeFlow REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {"User-Agent": "safeflow-sdk-python/1.0.0"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def health(self) -> dict[str, Any]:
        """Check API service health."""
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/v1/health", headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def list_policies(self) -> list[str]:
        """List available policy packs."""
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/v1/policies", headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("available_policies", [])

    def gate_image(
        self,
        image_bytes: bytes,
        pack: str = "general_video_platform",
        role: str = "analyst",
        actor_id: str = "sdk_actor",
        media_id: str = "sdk_media",
    ) -> dict[str, Any]:
        """Evaluate an uploaded avatar through the Profile Image Safety Gate."""
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "image_base64": b64_img,
            "pack_name": pack,
            "role": role,
            "actor_id": actor_id,
            "media_id": media_id,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/v1/gate", json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def evaluate_actor(
        self,
        actor_id: str,
        signals: Sequence[Signal | dict[str, Any]],
        policy_pack: str = "general_video_platform",
        role: str = "analyst",
    ) -> dict[str, Any]:
        """Evaluate actor signals and return explainable Decision."""
        serialized_signals = [
            s.model_dump(mode="json") if isinstance(s, Signal) else s
            for s in signals
        ]
        payload = {
            "actor_id": actor_id,
            "signals": serialized_signals,
            "policy_pack": policy_pack,
            "role": role,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/v1/evaluate", json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def queue_link(
        self,
        url: str,
        actor_id: str,
        actor_risk: RiskLevel | str = RiskLevel.LOW,
        delayed_activation_hours: float = 0.0,
        is_cloaked: bool = False,
    ) -> dict[str, Any]:
        """Submit an external destination link to the hold-and-verify queue."""
        risk_str = actor_risk.value if isinstance(actor_risk, RiskLevel) else str(actor_risk)
        payload = {
            "url": url,
            "actor_id": actor_id,
            "actor_risk": risk_str,
            "delayed_activation_hours": delayed_activation_hours,
            "is_cloaked": is_cloaked,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/v1/queue/links", json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def reveal_media(self, analyst_id: str, media_id: str) -> dict[str, Any]:
        """Request to unblur and inspect flagged media item."""
        payload = {"analyst_id": analyst_id, "media_id": media_id}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/v1/review/reveal", json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()
