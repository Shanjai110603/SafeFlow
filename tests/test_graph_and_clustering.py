"""Test suite for SafeFlow Graph and Clustering Engine (Milestone 4)."""

from __future__ import annotations

import pytest
from safeflow.adapters.synthetic.generator import GeneratorConfig, SyntheticGenerator
from safeflow.core.graph.bipartite import BipartiteCoTargetingEngine
from safeflow.core.graph.builder import HeterogeneousGraphBuilder
from safeflow.core.graph.clustering import CoordinationClusteringEngine
from safeflow.core.graph.eval import ClusterEvaluator


@pytest.mark.parametrize("profile", ["video_comments", "forum_communities", "chat_servers"])
@pytest.mark.parametrize("variant", ["A", "B"])
def test_graph_builder_and_clustering_pipeline(profile: str, variant: str):
    """Verify that the full graph and clustering pipeline builds cleanly across all profiles and variants."""
    cfg = GeneratorConfig(seed=303, variant=variant, platform_profile=profile, actor_count=120)  # type: ignore[arg-type]
    ds = SyntheticGenerator(cfg).generate()

    # 1. Build Heterogeneous Graph
    G = HeterogeneousGraphBuilder.build(
        actors=ds.actors,
        spaces=ds.spaces,
        contents=ds.content,
        media=ds.media,
        links=ds.links,
        relations=ds.relations,
    )

    assert len(G.nodes) > 0
    assert len(G.edges) > 0

    # 2. Bipartite Co-Targeting Projection
    co_graph = BipartiteCoTargetingEngine.compute_co_targeting_graph(G)
    assert len(co_graph.nodes) == len(ds.actors)

    # 3. Multi-Resource Actor Similarity Graph & Clustering
    actor_sim_graph = CoordinationClusteringEngine.build_actor_similarity_graph(G)
    clusters = CoordinationClusteringEngine.detect_clusters(actor_sim_graph, min_cluster_size=2)
    assert len(clusters) > 0, f"Expected clusters in {profile}_{variant}"

    # 4. Centrality Metrics
    metrics = CoordinationClusteringEngine.compute_network_metrics(actor_sim_graph)
    assert len(metrics) == len(ds.actors)

    # 5. Cluster Evaluation
    eval_res = ClusterEvaluator.evaluate(ds.actors, clusters)
    assert eval_res["ari"] >= 0.0
    assert eval_res["nmi"] >= 0.0
    assert eval_res["pairwise_precision"] >= 0.0

    # 6. Negative Control Isolation: Zero false merges for fandom and meme reuse
    assert eval_res["fandom_false_merges"] == 0, f"Fandom false merges in {profile}_{variant}: {eval_res['fandom_false_merges']}"
    assert eval_res["avatar_reuse_false_merges"] == 0, f"Meme avatar false merges in {profile}_{variant}: {eval_res['avatar_reuse_false_merges']}"
