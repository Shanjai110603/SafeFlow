# SafeFlow Project Plan & Milestone Roadmap

This document outlines the phased delivery of SafeFlow. Development follows a strict **vertical-slice-first** methodology: Milestones 0 through 6 must function end-to-end via CLI and pytest with zero frontend dependencies. Every milestone terminates at a formal verification Gate.

---

## Roadmap Overview

```
[M0: Foundations & Safety Docs]
           │
           ▼
[M1: Core Skeleton & Image Gate] ──► [GATE 1] ──► **USER REVIEW & STOP**
           │
           ▼
[M2: Synthetic Generator & Profiles] ──► [GATE 2]
           │
           ▼
[M3: Signal Plugins Suite] ──► [GATE 3]
           │
           ▼
[M4: Graph & Clustering Engine] ──► [GATE 4]
           │
           ▼
[M5: Explainable Decision Engine] ──► [GATE 5]
           │
           ▼
[M6: Evaluation Framework & Ablations] ──► [GATE 6]
           │
           ▼
[M7: Threat Simulation Lab & Link Hold] ──► [GATE 7]
           │
           ▼
[M8: REST API, SDK & Review Dashboard] ──► [GATE 8]
           │
           ▼
[M9: Privacy Controls, Reports & Packaging] ──► [FINAL DEMO]
```

---

## Milestone 0: Foundations, Governance & Architecture
- **Objective**: Establish safety rules, threat model, intended use posture, prior art analysis with verified licenses, architectural decisions, and project scaffolding.
- **Deliverables**:
  - `docs/ARCHITECTURE.md`
  - `docs/PLAN.md`
  - `docs/THREAT_MODEL.md`
  - `docs/RESPONSIBLE_RESEARCH.md`
  - `docs/INTENDED_USE.md`
  - `docs/PRIOR_ART.md`
  - `docs/DECISIONS.md`
  - `docs/STATUS.md`
  - `docs/IMAGE_POLICY.md`
  - Scaffolding: `pyproject.toml`, `.github/workflows/ci.yml`, `ruff`, `mypy`, `pytest` configs.
- **Gate 0 Criteria**: Scaffolding initializes, git repository cleanly configured, all foundation documents present and cross-referenced.

---

## Milestone 1: Core Skeleton & Profile Image Safety Gate
- **Objective**: Implement canonical Pydantic v2 schema, policy pack loader with invariant enforcement, plugin registry, audit logger with hash-chaining, generic role redactor, procedural avatar generator, `MockClassifier` with dual-crop scoring, upload hardening, in-memory `ReviewBlobStore`, and the `ImageGatePlugin`.
- **Deliverables**:
  - `safeflow/core/` (schema, config, database, registry, audit, roles, blob_store, fetcher)
  - `safeflow/plugins/image_gate/` (plugin, pipeline, classifier, label_maps)
  - `safeflow/utils/procedural_avatar.py`
  - `safeflow/cli/main.py` (`safeflow gate ...`, `safeflow schema export`)
  - `config/policies/` (5 core policy packs)
  - Comprehensive pytest suite.
- **Gate 1 Criteria**:
  1. `pytest tests/test_import_boundaries.py` passes (zero imports from adapters in core; plugins do not import each other).
  2. `pytest tests/test_image_gate_pipeline.py` passes:
     - NUDITY/EXPLICIT mock label triggers BLOCK; zero bytes persisted (verified by canary scan).
     - Perceptual hashes calculated for BLOCK before memory deallocation.
     - SUGGESTIVE mock label triggers ALLOW_TAGGED; internal tag logged, hidden from creator.
     - Score in review band triggers REVIEW; default avatar served; encrypted/blurred review item created.
     - Classifier error triggers fail-closed fallback; decision logged; no crash.
     - Display-crop score higher than full image is correctly selected (`crop_used="display_crop"`).
     - Known-bad simulated hash triggers immediate BLOCK.
     - Policy-pack test: identical mock scores evaluated under `general_video_platform` vs `youth_oriented_service` yield documented different outcomes.
     - Pack loader rejects adversarial packs violating non-overridable invariants.
  3. `pytest tests/test_image_robustness.py` passes (transforms, mirror indexing, pre-registered Hamming distances).
  4. `safeflow gate --file <path> --pack <name> --role analyst|creator` demonstrates correct outputs.
- **Enforcement Point**: **STOP execution after Milestone 1 and summarize for User Review.**

---

## Milestone 2: Synthetic Generator & Platform Profiles
- **Objective**: Build deterministic synthetic graph/activity generator producing canonical entities for Variants A (dev) and B (held-out) across three platform profiles: `video_comments`, `forum_communities`, and `chat_servers`.
- **Deliverables**:
  - `safeflow/adapters/synthetic/` generator module.
  - Category generators: Attack categories (`SPAM`, `CURIOSITY_FUNNEL`, `AI_IMAGE_NETWORK`, `IMAGE_REUSE_NETWORK`, `LINK_ABUSE`, `ACCOUNT_ROTATION`, `MIXED_ATTACK`, `HIJACKED_ACCOUNT`, `AGED_ACCOUNT_ATTACK`, `HUMAN_FARM`) and Legit categories (`NORMAL`, `NORMAL_HIGH_ENGAGEMENT`, `LEGIT_FANDOM`, `LEGIT_AVATAR_REUSE`, `LEGIT_LINK_CREATOR`, `LEGIT_SUGGESTIVE_AVATAR`).
  - Procedural avatars with sidecar ground-truth; mock `.local` destinations with cloaking, shorteners, and activation delay.
  - JSONL and SQLite exporters; `manifest.json`.
  - `safeflow/adapters/generic_jsonl/validator.py`.
- **Gate 2 Criteria**:
  - Determinism test passes (same seed -> byte-identical export).
  - Procedural avatar verification: zero scraped/real images.
  - Canonical JSON Schema validation passes on all three profiles.

---

## Milestone 3: Signal Plugins Suite
- **Objective**: Implement detection signal plugins conforming to `SignalPlugin` protocol.
- **Deliverables**:
  - `safeflow/plugins/media_reuse/`: pHash/dHash/wHash clustering, popularity discounting (IDF-style), weak AI-likelihood signal.
  - `safeflow/plugins/text_behavior/`: burst detection, comment diversity, repeated-phrase rate, TF-IDF cosine similarity, temporal trajectory.
  - `safeflow/plugins/targeting/`: concentration on high-popularity spaces normalized by space-popularity percentile, bipartite co-targeting risk ratio.
  - `safeflow/plugins/link_destination/`: URL structure, shortener detection, domain age, cloaking indicator, activation delay.
  - `safeflow/plugins/actor_profile/`: historical mutations in bio, links, and avatar.
- **Gate 3 Criteria**:
  - Unit tests prove: normal comments in funnels yield low comment-anomaly; legit avatar reuse yields low reuse signal after discounting; targeting signal does not fire on `NORMAL_HIGH_ENGAGEMENT`.

---

## Milestone 4: Graph & Clustering Engine
- **Objective**: Construct heterogeneous NetworkX graph over canonical entities and detect coordinated actor networks.
- **Deliverables**:
  - Heterogeneous graph builder (actors, spaces, content, media, links, domains).
  - Popularity-discounted actor-actor projection graph.
  - Community detection (Louvain / connected components), centrality metrics.
  - Bipartite co-visit overlap-vs-chance statistical testing (RCAT philosophy).
  - Cluster evaluation (ARI, NMI, pairwise precision/recall).
- **Gate 4 Criteria**:
  - Metrics reported honestly for Variants A and B on each profile.
  - Legit fandom and avatar reuse clusters verified not wrongly merged into attack clusters.

---

## Milestone 5: Explainable Decision Engine
- **Objective**: Multi-tiered decision engine combining heuristic baseline and calibrated classifier with strict signal-family gating.
- **Deliverables**:
  - Heuristic scorer (transparent weighted baseline).
  - Calibrated model (Logistic Regression with Platt calibration trained on Variant A with group-aware cluster splits, tested on B).
  - Signal-family gating: HIGH requires $\ge 3$ distinct families; CRITICAL requires $\ge 4$.
  - Single-signal protection: `suggestive_flag` or AI-likelihood alone can never elevate an actor above LOW.
  - Structured analyst-facing `Explanation` objects with counter-evidence.
- **Gate 5 Criteria**:
  - Scenario tests A–G pass.
  - Permanent regression passes: ALLOW_TAGGED avatar with zero other signals yields actor risk LOW.
  - Same actor evaluated under two policy packs yields identical signals but distinct recommendations.

---

## Milestone 6: Evaluation Framework & Ablations
- **Objective**: Rigorous empirical evaluation framework with zero invented figures.
- **Deliverables**:
  - `safeflow eval --seed <n> --variant <A|B> --profile <name>`
  - Precision, Recall, F1, PR-AUC, ROC-AUC, Precision@k.
  - Prevalence re-weighting (0.1%, 1%, 5%).
  - Ablation studies (comment-only, image-only, link-only, full system).
  - Cross-platform transfer matrix (trained on profile X, tested on Y and Z).
  - Export to `results/<run_id>/` (JSON, CSV, Markdown).
- **Gate 6 Criteria**:
  - Cross-platform generalization matrix generated and reproducible.
  - All outputs stamped with commit, seed, variant, and generator version.

---

## Milestone 7: Threat Simulation Lab & Link Verification Queue
- **Objective**: Interactive simulation lab and risk-adaptive link hold-and-verify queue.
- **Deliverables**:
  - Threat Simulation scenarios with ground-truth vs detected confusion matrix.
  - Simulated clock link verification queue with configurable windows (5m, 15m, 30m, 60m, 120m).
  - Tradeoff measurement: caught attack links vs legit creator delay vs cloaking.
- **Gate 7 Criteria**:
  - Tradeoff report generated and verified by tests.

---

## Milestone 8: REST API, SDK, Exporters & Analyst Dashboard
- **Objective**: Production-grade HTTP service, Python SDK client, T&S exporters, and React/Tailwind investigation UI.
- **Deliverables**:
  - FastAPI `/v1/...` endpoints with OpenAPI docs.
  - JSONL and webhook event exporters; Coop/Osprey interface compatibility notes.
  - Lightweight Python SDK (`safeflow-sdk`).
  - React/Vite dashboard: blurred previews by default, reveal tracking, network graph visualization, explanation explorer.
- **Gate 8 Criteria**:
  - API tests pass; frontend builds cleanly; smoke test validates UI against mock dataset.

---

## Milestone 9: Privacy Controls, Research Report & Packaging
- **Objective**: Data minimization, automated retention purge, research report generator, and wheel distribution.
- **Deliverables**:
  - `safeflow data delete` and `safeflow data export`.
  - Pseudonymization verification test.
  - Automated research report generator (`safeflow report`).
  - `docs/LIMITATIONS.md`.
  - Complete `README.md` with architecture diagrams and tutorials.
- **Definition of Done Verification**:
  - All Gates 1–8 verified.
  - Zero Section 1 safety rule violations.
  - Portability test passes (4th throwaway platform profile added without core edits).
