"""Graph Clustering and Multi-Resource Actor Coordination Engine."""

from __future__ import annotations

from typing import Any
import networkx as nx
from safeflow.core.graph.bipartite import BipartiteCoTargetingEngine


class CoordinationClusteringEngine:
    """Detects coordinated actor clusters across shared media, domains, and spaces."""

    @classmethod
    def build_actor_similarity_graph(
        cls,
        G: nx.MultiDiGraph,
        min_weight_threshold: float = 0.5,
    ) -> nx.Graph:
        """Construct a unified weighted Actor-Actor graph combining media reuse, shared domains, and co-targeting."""
        actor_graph = nx.Graph()

        # Add all Actor nodes
        for node, data in G.nodes(data=True):
            if data.get("node_type") == "Actor":
                actor_graph.add_node(node, **data)

        # 1. Add Shared Media / Hash Match Edges
        # Map media to actors
        media_actors: dict[str, list[str]] = {}
        for u, v, data in G.edges(data=True):
            if data.get("edge_type") == "uses_media":
                media_actors.setdefault(v, []).append(u)

        for m_id, actors in media_actors.items():
            if 1 < len(actors) < 50:  # Skip viral defaults/memes
                for i in range(len(actors)):
                    for j in range(i + 1, len(actors)):
                        a1, a2 = actors[i], actors[j]
                        cur_w = actor_graph[a1][a2]["weight"] if actor_graph.has_edge(a1, a2) else 0.0
                        actor_graph.add_edge(a1, a2, weight=cur_w + 3.0, reason="shared_media")

        # 2. Add Shared Destination Domain Edges
        # Traverse Actor -> Link -> Domain
        actor_domains: dict[str, set[str]] = {}
        for a_id in actor_graph.nodes():
            for _, link_id, d_edge in G.out_edges(a_id, data=True):
                if d_edge.get("edge_type") == "links_to":
                    for _, dom_id, r_edge in G.out_edges(link_id, data=True):
                        if r_edge.get("edge_type") == "routes_to":
                            actor_domains.setdefault(a_id, set()).add(dom_id)

        domain_actors: dict[str, list[str]] = {}
        for a_id, domains in actor_domains.items():
            for dom in domains:
                domain_actors.setdefault(dom, []).append(a_id)

        for dom, actors in domain_actors.items():
            if 1 < len(actors) < 40:
                for i in range(len(actors)):
                    for j in range(i + 1, len(actors)):
                        a1, a2 = actors[i], actors[j]
                        cur_w = actor_graph[a1][a2]["weight"] if actor_graph.has_edge(a1, a2) else 0.0
                        actor_graph.add_edge(a1, a2, weight=cur_w + 2.5, reason="shared_destination")

        # 3. Reinforce existing links with Bipartite Co-Targeting
        co_space_graph = BipartiteCoTargetingEngine.compute_co_targeting_graph(G)
        for u, v, data in co_space_graph.edges(data=True):
            rr = data.get("risk_ratio", 1.0)
            if actor_graph.has_edge(u, v) and rr > 1.5:
                # Corroborate existing media/destination link with co-targeting
                actor_graph[u][v]["weight"] += min(2.0, rr * 0.5)

        # Prune edges below min_weight_threshold
        pruned_edges = [(u, v) for u, v, d in actor_graph.edges(data=True) if d.get("weight", 0.0) < min_weight_threshold]
        actor_graph.remove_edges_from(pruned_edges)

        return actor_graph

    @classmethod
    def detect_clusters(
        cls,
        actor_graph: nx.Graph,
        min_cluster_size: int = 2,
    ) -> dict[str, list[str]]:
        """Detect coordinated clusters using Louvain modularity or connected components."""
        clusters: dict[str, list[str]] = {}
        cluster_id = 0

        # Subgraph of connected nodes
        active_nodes = [n for n in actor_graph.nodes() if actor_graph.degree(n) > 0]
        if not active_nodes:
            return clusters

        subG = actor_graph.subgraph(active_nodes)

        try:
            # Use Louvain modularity community detection
            communities = nx.community.louvain_communities(subG, weight="weight", seed=42)
        except Exception:
            # Fallback to connected components
            communities = list(nx.connected_components(subG))

        for comm in communities:
            if len(comm) >= min_cluster_size:
                cluster_id += 1
                c_name = f"detected_cluster_{cluster_id:03d}"
                clusters[c_name] = sorted(list(comm))

        return clusters

    @classmethod
    def compute_network_metrics(cls, actor_graph: nx.Graph) -> dict[str, dict[str, float]]:
        """Compute node-level centrality metrics (degree, eigenvector/pagerank)."""
        metrics: dict[str, dict[str, float]] = {}
        if len(actor_graph) == 0:
            return metrics

        deg = dict(actor_graph.degree(weight="weight"))
        try:
            pr = nx.pagerank(actor_graph, weight="weight")
        except Exception:
            pr = {n: 1.0 / len(actor_graph) for n in actor_graph.nodes()}

        for n in actor_graph.nodes():
            metrics[n] = {
                "degree_centrality": round(float(deg.get(n, 0.0)), 4),
                "pagerank": round(float(pr.get(n, 0.0)), 4),
            }

        return metrics
