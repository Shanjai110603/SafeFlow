"""Tests for SafeFlow Advanced Features:
1. ActivityPub/Fediverse Platform Adapter
2. Fast Perceptual Hash BK-Tree Indexing
3. Appeals-to-Calibration Active Learning Pipeline
4. High-Throughput Concurrency & Stress Testing
"""

import numpy as np
import pytest
from sqlalchemy.orm import Session

from safeflow.adapters.activitypub import ActivityPubAdapter
from safeflow.core.database import AppealRecord, DatabaseManager
from safeflow.core.decision.active_learning import ActiveLearningPipeline
from safeflow.core.decision.calibrated import CalibratedScorer
from safeflow.core.hashing_index import PerceptualHashBKTree, hamming_distance_hex
from safeflow.lab.stress import SafeFlowStressTester


@pytest.fixture
def db_session():
    db = DatabaseManager(db_url="sqlite:///:memory:")
    with db.get_session() as session:
        yield session


def test_activitypub_adapter_actor_and_note_ingest():
    adapter = ActivityPubAdapter()
    assert adapter.platform_id == "activitypub_fediverse"

    # Test Actor object
    actor_payload = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Person",
        "id": "https://mastodon.social/users/alice_test",
        "preferredUsername": "alice_test",
        "name": "Alice Wonderland",
        "summary": "Check out my funnels at https://funnel.activitypub.local for updates!",
        "icon": {
            "type": "Image",
            "url": "https://mastodon.social/system/accounts/avatars/alice.png",
        },
    }

    res_actor = adapter.ingest(actor_payload)
    assert len(res_actor["actors"]) == 1
    assert res_actor["actors"][0].platform_id == "activitypub_fediverse"
    assert len(res_actor["media"]) == 1
    assert res_actor["media"][0].role == "avatar"
    assert len(res_actor["links"]) == 1
    assert res_actor["links"][0].domain == "funnel.activitypub.local"

    # Test Note object
    note_payload = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Create",
        "actor": "https://mastodon.social/users/alice_test",
        "object": {
            "type": "Note",
            "id": "https://mastodon.social/users/alice_test/statuses/109348923",
            "content": "Hello Fediverse! This is a test post.",
            "inReplyTo": "https://mastodon.social/users/bob/statuses/998877",
            "attachment": [
                {
                    "type": "Document",
                    "url": "https://mastodon.social/media/attachment1.jpg",
                }
            ],
        },
    }

    res_note = adapter.ingest(note_payload)
    assert len(res_note["contents"]) == 1
    assert res_note["contents"][0].kind.value == "comment"
    assert len(res_note["media"]) == 1


def test_perceptual_hash_bktree_indexing_and_search():
    tree = PerceptualHashBKTree()
    assert len(tree) == 0

    hashes = [
        ("0x0000000000000000", "zero_hash"),
        ("0x0000000000000001", "dist_1_from_zero"),
        ("0x0000000000000003", "dist_2_from_zero"),
        ("0x0000000000000007", "dist_3_from_zero"),
        ("0xffffffffffffffff", "all_ones_far"),
        ("0xaaaaaaaaaaaaaaaa", "alternating_bits"),
    ]

    for h_str, label in hashes:
        tree.insert(h_str, {"label": label})

    assert len(tree) == len(hashes)

    # Search query near zero
    query = "0x0000000000000000"
    matches_radius_2 = tree.search(query, max_distance=2)

    matched_labels = [m["payload"]["label"] for m in matches_radius_2]
    assert "zero_hash" in matched_labels
    assert "dist_1_from_zero" in matched_labels
    assert "dist_2_from_zero" in matched_labels
    assert "all_ones_far" not in matched_labels

    # Verify sorting by distance
    distances = [m["distance"] for m in matches_radius_2]
    assert distances == sorted(distances)


def test_appeals_to_calibration_active_learning(db_session: Session):
    # 1. Insert overturned and upheld appeal records
    db_session.add(AppealRecord(
        appeal_id="app_false_pos_1",
        actor_id="actor_fp_1",
        media_id="med_fp_1",
        status="OVERTURNED",
        reason="Legitimate creator mistakenly flagged",
    ))
    db_session.add(AppealRecord(
        appeal_id="app_true_pos_1",
        actor_id="actor_tp_1",
        media_id="med_tp_1",
        status="UPHELD",
        reason="Confirmed multi-hop spam network",
    ))
    db_session.commit()

    # 2. Extract feedback
    feedback = ActiveLearningPipeline.extract_appeal_feedback(db_session)
    assert len(feedback) == 2
    overturned = next(f for f in feedback if f["appeal_id"] == "app_false_pos_1")
    upheld = next(f for f in feedback if f["appeal_id"] == "app_true_pos_1")
    assert overturned["target_label"] == 0  # Hard negative
    assert upheld["target_label"] == 1      # Confirmed attack

    # 3. Simulate retraining with feedback
    np.random.seed(42)
    base_X = np.random.randn(50, 5)
    base_y = (base_X[:, 0] + base_X[:, 1] > 0).astype(int)

    feedback_X = np.array([
        [0.8, 0.2, 0.1, 0.0, 0.0],  # FP sample
        [0.9, 0.9, 0.8, 0.7, 0.9],  # TP sample
    ])
    feedback_y = np.array([0, 1])

    scorer = CalibratedScorer(feature_names=["f1", "f2", "f3", "f4", "f5"])
    scorer.fit(base_X, base_y)

    retrain_res = ActiveLearningPipeline.retrain_with_feedback(
        scorer=scorer,
        base_features=base_X,
        base_labels=base_y,
        feedback_features=feedback_X,
        feedback_labels=feedback_y,
    )

    assert retrain_res["status"] == "RETRAINED"
    assert retrain_res["samples_added"] == 2
    assert retrain_res["total_samples"] == 52


def test_stress_tester_concurrency_and_latency():
    res = SafeFlowStressTester.run_decision_engine_benchmark(
        concurrency=10,
        total_requests=100,
        actor_id_prefix="unit_test_stress",
    )

    assert res["total_requests"] == 100
    assert res["concurrency"] == 10
    assert res["throughput_rps"] > 0
    assert res["latency_p50_ms"] >= 0
    assert res["latency_p99_ms"] >= res["latency_p50_ms"]
