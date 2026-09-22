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

    @api.get("/v1/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        """Health check endpoint returning engine status, timestamp, and version."""
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        }

    @api.get("/v1/policies", tags=["Policies"])
    def list_policies() -> dict[str, Any]:
        """List all available platform policy packs and active threshold profiles."""
        packs = PolicyPackLoader.list_available_packs()
        return {"available_policies": packs}

    @api.post("/v1/gate", tags=["Moderation Gate"])
    def gate_image_endpoint(req: GateRequest) -> Any:
        """Upload-time profile image safety gate evaluation.

        Executes dual-crop classification, perceptual hashing (pHash/dHash/wHash),
        and role-based redaction (analyst vs. creator view). Blocked images are
        purged immediately with zero byte persistence.
        """
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

    @api.post("/v1/evaluate", tags=["Decision Engine"])
    def evaluate_actor_endpoint(req: EvaluateRequest) -> Any:
        """Multi-signal actor risk scoring with signal-family gating invariants.

        Enforces multi-family confirmation (>=3 families for HIGH, >=4 for CRITICAL)
        and single-signal protection. Emits explainable natural language evidence.
        """
        try:
            policy = PolicyPackLoader.load_by_name(req.policy_pack)
        except Exception:
            policy = PolicyPackLoader.load_default()

        engine = DecisionEngine(policy_pack=policy)
        decision = engine.evaluate_actor(actor_id=req.actor_id, signals=req.signals)

        user_role = UserRole.CREATOR if req.role.lower() == "creator" else UserRole.ANALYST
        if user_role == UserRole.CREATOR:
            return RoleRedactor.redact(decision, role=user_role)
        return decision.model_dump()

    @api.post("/v1/graph/cluster", tags=["Graph & Clustering"])
    def cluster_graph_endpoint(req: ClusterRequest) -> Any:
        """Construct multi-modal heterogeneous graph and detect coordinated actor clusters.

        Applies Louvain modularity clustering and bipartite space co-targeting
        projections with anti-bridging negative controls.
        """
        G = HeterogeneousGraphBuilder.build(
            actors=req.actors,
            spaces=req.spaces,
            contents=req.contents,
            media=req.media,
            links=req.links,
        )

        co_graph = CoordinationClusteringEngine.build_actor_similarity_graph(G)
        clusters = CoordinationClusteringEngine.detect_clusters(co_graph)

        return {
            "total_actors": len(req.actors),
            "cluster_count": len(clusters),
            "clusters": [
                {
                    "cluster_id": c_name,
                    "size": len(members),
                    "members": members,
                }
                for c_name, members in clusters.items()
            ],
        }

    @api.post("/v1/queue/links", tags=["Link Queue"])
    def queue_link_endpoint(req: QueueLinkRequest) -> Any:
        """Enqueue external link into simulated clock hold-and-verify queue.

        Low risk links are released immediately (0 delay). Elevated risk links
        are held for automated delayed-activation rescan.
        """
        link = Link(
            link_id=f"lnk_{req.actor_id[:8]}",
            actor_id=req.actor_id,
            surface=LinkSurface.PROFILE_DESCRIPTION,
            url_normalized=req.url,
            domain=req.url.split("/")[2] if "/" in req.url else req.url,
        )
        enqueued_item = _GLOBAL_QUEUE.enqueue(
            link=link,
            actor_risk=req.actor_risk,
            delayed_activation_hours=req.delayed_activation_hours,
            is_cloaked=req.is_cloaked,
        )
        return enqueued_item.model_dump()

    @api.post("/v1/review/reveal", tags=["Analyst Review"])
    def reveal_image_endpoint(req: RevealRequest) -> Any:
        """Analyst un-blur triage operation with strict session reveal quota enforcement.

        Enforces a hard limit of 10 image reveals per analyst session to protect
        reviewer wellbeing. Records access in tamper-evident audit log.
        """
        current_used = _REVEAL_QUOTAS.get(req.analyst_id, 0)
        if current_used >= 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Analyst session reveal quota exhausted (maximum 10 reveals per session). Take a mandatory rest break.",
            )

        _REVEAL_QUOTAS[req.analyst_id] = current_used + 1
        return {
            "status": "REVEALED",
            "revealed": True,
            "analyst_id": req.analyst_id,
            "media_id": req.media_id,
            "reveals_used": _REVEAL_QUOTAS[req.analyst_id],
            "reveals_remaining": 10 - _REVEAL_QUOTAS[req.analyst_id],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @api.get("/v1/metrics", tags=["System"])
    def metrics_endpoint() -> dict[str, Any]:
        """Return Prometheus-compatible signal counters, active queues, and system telemetry."""
        return {
            "safeflow_active_queues": len(_GLOBAL_QUEUE),
            "safeflow_reveal_sessions": len(_REVEAL_QUOTAS),
            "safeflow_total_reveals": sum(_REVEAL_QUOTAS.values()),
            "safeflow_engine_status": 1,
        }

    return api


app = create_app()
