"""Bipartite Co-visit and Co-targeting Projection Engine."""

from __future__ import annotations

from collections import Counter
import math
from typing import Any
import networkx as nx


class BipartiteCoTargetingEngine:
    """Builds bipartite projections and calculates overlap-vs-chance risk ratios."""

    @classmethod
    def compute_co_targeting_graph(
        cls,
        G: nx.MultiDiGraph,
        min_co_occurrences: int = 1,
    ) -> nx.Graph:
        """Compute weighted Actor-Actor projection based on shared targeted spaces with popularity discounting."""
        co_graph = nx.Graph()

        # Extract Actor -> Spaces mapping
        actor_spaces: dict[str, set[str]] = {}
        space_popularity: dict[str, float] = {}
        all_actors: list[str] = []

        for node, data in G.nodes(data=True):
            if data.get("node_type") == "Actor":
                all_actors.append(node)
                co_graph.add_node(node, **data)
            elif data.get("node_type") == "Space":
                space_popularity[node] = data.get("popularity_percentile", 50.0)

        for u, v, data in G.edges(data=True):
            if data.get("edge_type") == "targets_space":
                actor_spaces.setdefault(u, set()).add(v)

        total_spaces = len(space_popularity) or 1
        num_actors = len(all_actors) or 1

        # Space frequency across population for IDF weighting
        space_actor_counts: Counter[str] = Counter()
        for spaces in actor_spaces.values():
            for s in spaces:
                space_actor_counts[s] += 1

        # Compute pairwise weighted co-targeting
        for i, a1 in enumerate(all_actors):
            spaces_1 = actor_spaces.get(a1, set())
            if not spaces_1:
                continue

            for a2 in all_actors[i + 1:]:
                spaces_2 = actor_spaces.get(a2, set())
                if not spaces_2:
                    continue

                shared = spaces_1.intersection(spaces_2)
                if len(shared) < min_co_occurrences:
                    continue

                # Popularity-discounted weight
                # Shared niche spaces contribute high weight; shared universal top spaces contribute lower weight
                weight = 0.0
                for s in shared:
                    freq = space_actor_counts[s]
                    # IDF weight
                    idf = math.log(1.0 + num_actors / (1.0 + freq))
                    weight += idf

                # Expected overlap under independence
                expected_overlap = sum(
                    (space_actor_counts[s] / num_actors) ** 2 for s in (spaces_1 | spaces_2)
                )
                observed_overlap = len(shared)
                risk_ratio = (observed_overlap + 0.01) / (expected_overlap + 0.01)

                co_graph.add_edge(
                    a1,
                    a2,
                    weight=round(weight, 4),
                    shared_spaces_count=len(shared),
                    risk_ratio=round(risk_ratio, 4),
                )

        return co_graph
