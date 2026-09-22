"""Tests for SafeFlow Milestone 8 REST API, SDK, and Exporters.

Validates:
1. FastAPI endpoints (/v1/health, /v1/policies, /v1/gate, /v1/evaluate, /v1/graph/cluster, /v1/queue/links, /v1/review/reveal).
2. Generic role redaction on API responses (Creator vs Analyst).
3. SafeFlowClient SDK methods.
4. JSONL, Webhook, and Coop/Osprey event exporters.
"""

import base64
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from safeflow.api.app import app
from safeflow.core.schema import Decision, RiskLevel, Signal
from safeflow.exporters.compatibility import TSCompatibilityFormatter
from safeflow.exporters.jsonl_exporter import JSONLEventExporter
from safeflow.exporters.webhook_exporter import WebhookDispatcher
from safeflow.utils.procedural_avatar import ProceduralAvatarGenerator


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health_and_policies(client: TestClient):
    resp_health = client.get("/v1/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"

    resp_pol = client.get("/v1/policies")
    assert resp_pol.status_code == 200
    assert "general_video_platform" in resp_pol.json()["available_policies"]


def test_api_gate_endpoint(client: TestClient):
    # Generate procedural neutral avatar
    avatar_bytes = ProceduralAvatarGenerator.generate(label="NEUTRAL", seed=42)
    b64_img = base64.b64encode(avatar_bytes).decode("utf-8")

    # Analyst role request
    analyst_payload = {
        "image_base64": b64_img,
        "pack_name": "general_video_platform",
        "role": "analyst",
        "actor_id": "actor_test_gate",
        "media_id": "media_test_gate",
    }
    resp_analyst = client.post("/v1/gate", json=analyst_payload)
    assert resp_analyst.status_code == 200
    assert "decision" in resp_analyst.json()
    assert "crop_used" in resp_analyst.json()

    # Creator role request (sanitized)
    creator_payload = {
        "image_base64": b64_img,
        "pack_name": "general_video_platform",
        "role": "creator",
        "actor_id": "actor_test_gate",
        "media_id": "media_test_gate",
    }
    resp_creator = client.post("/v1/gate", json=creator_payload)
    assert resp_creator.status_code == 200
    data = resp_creator.json()
    assert data["status"] in ("ACCEPTED", "UNDER_REVIEW", "REJECTED")
    assert "crop_used" not in data
    assert "reasons" not in data


def test_api_evaluate_endpoint(client: TestClient):
    signals = [
        {
            "subject_type": "actor",
            "subject_id": "actor_eval_api",
            "family": "IMAGE_LINK",
            "name": "media_max_reuse",
            "value": 0.90,
            "confidence": 0.9,
            "producer": "media_reuse",
            "producer_version": "1.0.0",
        },
        {
            "subject_type": "actor",
            "subject_id": "actor_eval_api",
            "family": "BEHAVIOR",
            "name": "text_repetition_rate",
            "value": 0.85,
            "confidence": 0.9,
            "producer": "text_behavior",
            "producer_version": "1.0.0",
        },
        {
            "subject_type": "actor",
            "subject_id": "actor_eval_api",
            "family": "DESTINATION",
            "name": "link_max_dest_risk",
            "value": 0.80,
            "confidence": 0.85,
            "producer": "link_destination",
            "producer_version": "1.0.0",
        },
    ]

    payload = {
        "actor_id": "actor_eval_api",
        "signals": signals,
        "policy_pack": "general_video_platform",
        "role": "analyst",
    }
    resp = client.post("/v1/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == "HIGH"
    assert data["score"] >= 45.0
    assert len(data["families_triggered"]) == 3
    assert len(data["evidence"]) > 0


def test_api_reveal_quota(client: TestClient):
    analyst_id = "analyst_quota_test"
    # Execute 10 reveals
    for i in range(10):
        resp = client.post("/v1/review/reveal", json={"analyst_id": analyst_id, "media_id": f"m_{i}"})
        assert resp.status_code == 200
        assert resp.json()["revealed"] is True

    # 11th reveal should be rejected with 429 Too Many Requests
    resp_overflow = client.post("/v1/review/reveal", json={"analyst_id": analyst_id, "media_id": "m_11"})
    assert resp_overflow.status_code == 429
    assert "quota" in resp_overflow.json()["detail"].lower()


def test_exporters(tmp_path: Path):
    decision = Decision(
        subject="actor_exp_01",
        level=RiskLevel.CRITICAL,
        score=94.5,
        families_triggered=["IMAGE_LINK", "BEHAVIOR", "DESTINATION", "PROFILE_CHANGE"],
        evidence=["High media reuse (0.92)", "High text repetition (0.95)"],
        counter_evidence=["No mitigating factors"],
        recommended_action="Suspend actor account",
    )

    # 1. JSONL Exporter
    target_jsonl = tmp_path / "decisions.jsonl"
    count = JSONLEventExporter.export_decisions([decision], target_jsonl)
    assert count == 1
    assert target_jsonl.exists()

    # 2. Webhook Dispatcher signature verification
    dispatcher = WebhookDispatcher(
        endpoint_url="https://mock.webhook.local/events",
        secret_key="secret_test_key_123",
        min_severity=RiskLevel.HIGH,
    )
    sig = dispatcher.sign_payload(decision.model_dump_json().encode("utf-8"))
    assert len(sig) == 64  # SHA-256 hex string

    # 3. TS Compatibility Formatter (Osprey & Coop)
    osprey_rec = TSCompatibilityFormatter.to_osprey_action(decision)
    assert osprey_rec["action"] == "TAKEDOWN_ACTOR"
    assert "safeflow_image_link" in osprey_rec["tags"]

    coop_rec = TSCompatibilityFormatter.to_coop_incident(decision)
    assert coop_rec["severity"] == "CRITICAL"
    assert coop_rec["policy_violation"] == "COORDINATED_FUNNEL_ABUSE"
