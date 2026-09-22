"""Heterogeneous Graph Builder for Canonical SafeFlow Entities."""

from __future__ import annotations

from typing import Any
import networkx as nx
from safeflow.core.schema import Actor, Content, Link, Media, Relation, Space


class HeterogeneousGraphBuilder:
    """Constructs a rich NetworkX graph over canonical SafeFlow entities."""

    @classmethod
    def build(
        cls,
        actors: list[Actor],
        spaces: list[Space],
        contents: list[Content],
        media: list[Media],
        links: list[Link],
        relations: list[Relation] | None = None,
    ) -> nx.MultiDiGraph:
        """Build heterogeneous MultiDiGraph connecting all platform entities."""
        G = nx.MultiDiGraph()

        # 1. Add Actor Nodes
        for a in actors:
            G.add_node(
                a.actor_id,
                node_type="Actor",
                platform_id=a.platform_id,
                created_at=a.created_at.isoformat(),
                display_name_hash=a.display_name_hash,
                attributes=a.attributes,
            )

        # 2. Add Space Nodes
        for s in spaces:
            G.add_node(
                s.space_id,
                node_type="Space",
                kind=s.kind.value,
                parent_space_id=s.parent_space_id,
                popularity_percentile=s.popularity.percentile,
                audience_context=s.audience_context.value,
            )
            if s.parent_space_id:
                G.add_edge(s.space_id, s.parent_space_id, edge_type="child_of")

        # 3. Add Media Nodes & Edges
        for m in media:
            G.add_node(
                m.media_id,
                node_type="Media",
                role=m.role.value,
                phash=m.perceptual_hashes.get("phash", ""),
                gate_result=m.gate_result.value if m.gate_result else "ALLOW",
                tags=[t.name for t in m.tags],
            )
            G.add_edge(m.actor_id, m.media_id, edge_type="uses_media")

        # 4. Add Content Nodes & Edges
        for c in contents:
            G.add_node(
                c.content_id,
                node_type="Content",
                kind=c.kind.value,
                created_at=c.created_at.isoformat(),
                text=c.text,
            )
            G.add_edge(c.actor_id, c.content_id, edge_type="authored")
            G.add_edge(c.content_id, c.space_id, edge_type="posted_in")
            # Shortcut direct edge: Actor -> Space
            G.add_edge(c.actor_id, c.space_id, edge_type="targets_space", content_id=c.content_id, ts=c.created_at.isoformat())

        # 5. Add Link & Domain Nodes & Edges
        for l in links:
            G.add_node(
                l.link_id,
                node_type="Link",
                url_normalized=l.url_normalized,
                domain=l.domain,
                surface=l.surface.value,
                redirect_chain=l.redirect_chain,
            )
            G.add_edge(l.actor_id, l.link_id, edge_type="links_to")

            # Add domain node
            domain_node_id = f"dom_{l.domain}"
            if not G.has_node(domain_node_id):
                G.add_node(domain_node_id, node_type="Domain", name=l.domain)
            G.add_edge(l.link_id, domain_node_id, edge_type="routes_to")

        # 6. Add Relations
        if relations:
            for r in relations:
                G.add_edge(r.src, r.dst, edge_type=r.type.value, ts=r.ts.isoformat())

        return G
