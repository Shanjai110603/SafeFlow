"""Production-grade FastAPI HTTP service for SafeFlow."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Literal
from fastapi import FastAPI, HTTPException, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from safeflow.core.config import PolicyPackLoader
from safeflow.core.decision.engine import DecisionEngine
from safeflow.core.graph.builder import HeterogeneousGraphBuilder
from safeflow.core.graph.clustering import CoordinationClusteringEngine
from safeflow.core.roles import RoleRedactor, UserRole
from safeflow.core.schema import (
    Actor,
    Content,
    Decision,
    Link,
    LinkSurface,
    Media,
    RiskLevel,
    Signal,
    Space,
)
from safeflow.lab.models import QueueItem
from safeflow.lab.queue import LinkVerificationQueue
from safeflow.plugins.image_gate.pipeline import ImageGatePipeline


# Shared in-memory queue for API operations
_GLOBAL_QUEUE = LinkVerificationQueue(default_window_minutes=30)
_REVEAL_QUOTAS: dict[str, int] = {}  # analyst_id -> reveals_used (max 10)


class GateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_base64: str
    pack_name: str = "general_video_platform"
    role: str = "analyst"
    actor_id: str = "api_actor"
    media_id: str = "api_media"


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    signals: list[Signal]
    policy_pack: str = "general_video_platform"
    role: str = "analyst"


class ClusterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actors: list[Actor]
    spaces: list[Space] = Field(default_factory=list)
    contents: list[Content] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)


class QueueLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    actor_id: str
    actor_risk: RiskLevel = RiskLevel.LOW
    delayed_activation_hours: float = 0.0
    is_cloaked: bool = False


class RevealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analyst_id: str
    media_id: str


def create_app() -> FastAPI:
    """FastAPI Application factory for SafeFlow."""
    api = FastAPI(
        title="SafeFlow API",
        description="Platform-Agnostic Trust & Safety Signal and Decision Engine.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.get("/v1/health")
    def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        }

    @api.get("/v1/policies")
    def list_policies() -> dict[str, Any]:
        packs = PolicyPackLoader.list_available_packs()
        return {"available_policies": packs}

    @api.post("/v1/gate")
    def gate_image_endpoint(req: GateRequest) -> Any:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")

        try:
            policy = PolicyPackLoader.load_by_name(req.pack_name)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Policy pack error: {e}")

        pipeline = ImageGatePipeline()
        result = pipeline.process(
            image_bytes=image_bytes,
            policy_pack=policy,
            actor_id=req.actor_id,
            media_id=req.media_id,
        )

        user_role = UserRole.CREATOR if req.role.lower() == "creator" else UserRole.ANALYST
        if user_role == UserRole.CREATOR:
            resp = RoleRedactor.to_creator_response(
                decision=result.decision,
                media_id=req.media_id,
            )
            return resp.model_dump()
        else:
            return result.model_dump()

    @api.post("/v1/evaluate")
    def evaluate_actor_endpoint(req: EvaluateRequest) -> Any:
        try:
            policy = PolicyPackLoader.load_by_name(req.policy_pack)
        except Exception:
            policy = PolicyPackLoader.load_default()

        engine = DecisionEngine(policy_pack=policy)
        decision = engine.evaluate_actor(actor_id=req.actor_id, signals=req.signals)

        user_role = UserRole.CREATOR if req.role.lower() == "creator" else UserRole.ANALYST
        redacted = RoleRedactor.redact(decision, user_role)
        return redacted

    @api.post("/v1/graph/cluster")
    def cluster_endpoint(req: ClusterRequest) -> dict[str, Any]:
        G = HeterogeneousGraphBuilder.build(
            actors=req.actors,
            spaces=req.spaces,
            contents=req.contents,
            media=req.media,
            links=req.links,
        )
        sim_graph = CoordinationClusteringEngine.build_actor_similarity_graph(G)
        clusters = CoordinationClusteringEngine.detect_clusters(sim_graph, min_cluster_size=2)
        metrics = CoordinationClusteringEngine.compute_network_metrics(sim_graph)

        return {
            "cluster_count": len(clusters),
            "clusters": clusters,
            "network_metrics": metrics,
        }

    @api.post("/v1/queue/links")
    def queue_link_endpoint(req: QueueLinkRequest) -> dict[str, Any]:
        link = Link(
            link_id=f"link_{req.actor_id[:8]}",
            actor_id=req.actor_id,
            surface=LinkSurface.PROFILE_DESCRIPTION,
            url_normalized=req.url,
            domain=req.url.split("/")[2] if "/" in req.url else req.url,
        )
        item = _GLOBAL_QUEUE.enqueue(
            link=link,
            actor_risk=req.actor_risk,
            is_attack_ground_truth=(req.actor_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)),
            delayed_activation_hours=req.delayed_activation_hours,
            is_cloaked=req.is_cloaked,
        )
        return item.model_dump()

    @api.post("/v1/review/reveal")
    def reveal_media_endpoint(req: RevealRequest) -> dict[str, Any]:
        current_used = _REVEAL_QUOTAS.get(req.analyst_id, 0)
        if current_used >= 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Analyst '{req.analyst_id}' has reached the maximum per-session reveal quota (10/10)",
            )

        _REVEAL_QUOTAS[req.analyst_id] = current_used + 1
        return {
            "media_id": req.media_id,
            "revealed": True,
            "reveals_used": current_used + 1,
            "reveals_remaining": 10 - (current_used + 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @api.get("/v1/metrics")
    def metrics_endpoint() -> dict[str, Any]:
        return {
            "queue_items_total": len(_GLOBAL_QUEUE.items),
            "queue_pending": sum(1 for i in _GLOBAL_QUEUE.items if i.status.value == "PENDING"),
            "reveals_logged": sum(_REVEAL_QUOTAS.values()),
            "active_analysts": len(_REVEAL_QUOTAS),
        }

    return api


app = create_app()
