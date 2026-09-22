# SafeFlow Complete Project & Developer Guide

SafeFlow is an open, platform-agnostic trust & safety signal and decision engine designed to detect coordinated redirection funnels that direct users toward age-inappropriate destinations.

This guide provides step-by-step instructions on how to install, run, use, integrate, test, and benchmark the SafeFlow engine.

---

## Table of Contents

1. [System Architecture & Core Concept](#1-system-architecture--core-concept)
2. [Prerequisites & Requirements](#2-prerequisites--requirements)
3. [Installation](#3-installation)
4. [Interactive CLI Usage](#4-interactive-cli-usage)
5. [Running the REST API & Web Dashboard](#5-running-the-rest-api--web-dashboard)
6. [Python SDK Integration Guide](#6-python-sdk-integration-guide)
7. [Running Tests & Verifying Invariants](#7-running-tests--verifying-invariants)
8. [Threat Simulation & Link Queue](#8-threat-simulation--link-queue)
9. [Platform Adapters & Custom Integrations](#9-platform-adapters--custom-integrations)
10. [Defensive Browser Extension](#10-defensive-browser-extension)
11. [Privacy & GDPR Operations](#11-privacy--gdpr-operations)
12. [Troubleshooting & FAQ](#12-troubleshooting--faq)

---

## 1. System Architecture & Core Concept

Traditional Trust & Safety classifiers examine comments in isolation. Adversaries bypass these systems by decoupling promotion across multiple hops:

```
[Attention Surface] ──► [Identity Surface] ──► [Secondary Surface] ──► [Destination Surface]
(Normal comment on       (Suggestive avatar,     (Profile bio link,     (Multi-hop redirects,
 popular video)          obfuscated handle)      intermediate hub)      cloaked destination)
```

SafeFlow connects signals across the full pathway:
- **Profile Image Safety Gate**: Multi-crop evaluation with perceptual hashing (`pHash`, `dHash`, `wHash`) and canary-scanned zero image persistence on blocks.
- **Signal Extraction Plugins**: Text repetition, space popularity targeting concentration, redirect chain analysis, homoglyph density, and media reuse with IDF popularity discounting.
- **Graph & Clustering Engine**: Heterogeneous graph builder and Louvain community detection to uncover coordinated botnets without false merges on benign viral trends.
- **Explainable Decision Engine**: Mathematical multi-family gating (3+ families for `HIGH`, 4+ for `CRITICAL`) with role-based redaction (`creator` vs. `analyst`).

---

## 2. Prerequisites & Requirements

- **Operating System**: Linux, macOS, or Windows.
- **Python**: Version 3.11, 3.12, or 3.13.
- **Git**: Installed and configured.

---

## 3. Installation

### Option A: Standard Virtual Environment (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Shanjai110603/SafeFlow.git
cd SafeFlow

# 2. Create and activate a virtual environment
# On Linux/macOS:
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install SafeFlow in editable mode with development dependencies
pip install -e ".[dev]"
```

### Option B: Verification

Verify that the CLI is installed and accessible:

```bash
python -m safeflow.cli.main --help
# or simply:
safeflow --help
```

---

## 4. Interactive CLI Usage

SafeFlow comes with a suite of command-line tools for testing, benchmarking, and simulation:

### 1. Interactive 20-Actor Walkthrough Demo

Simulates a heterogeneous batch of 20 actors (benign creators, fandom users, spammers, and coordinated attack accounts) and evaluates them in real time:

```bash
safeflow demo --profile video_comments
```

### 2. Profile Image Safety Gate

Evaluate an avatar image against a policy pack:

```bash
# Analyst view (shows scores, crop breakdown, internal tags, and model metadata)
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role analyst

# Creator view (generic status message, scores and internal tags stripped)
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role creator
```

### 3. Synthetic Benchmark Dataset Generation

Generate deterministic, canonical synthetic datasets with ground truth:

```bash
# Generate 500 actors for video_comments profile (Variant A)
safeflow generate --profile video_comments --variant A --actors 500 --seed 42 --out datasets/

# Validate dataset compliance against canonical JSON schemas
safeflow validate-dataset --dir datasets/video_comments_A
```

### 4. Full Benchmark Evaluation & Ablation Sweep

Run end-to-end benchmark scoring, component ablations, and cross-platform transfer matrices:

```bash
safeflow eval --profile video_comments --seed 42 --actors 200 --out results/
```

### 5. High-Throughput Concurrency & Stress Testing

Measure decision engine throughput (req/s) and P50/P90/P95/P99 latency percentiles across multiple worker threads:

```bash
safeflow stress --concurrency 20 --requests 1000
```

### 6. Compile Research Report

Compile an automated, audit-stamped Markdown research report:

```bash
safeflow report --out docs/RESEARCH_REPORT.md
```

---

## 5. Running the REST API & Web Dashboard

SafeFlow includes a production-ready FastAPI service and an interactive dark-mode Trust & Safety Investigation Web Console.

### Starting the Server

```bash
safeflow serve --host 127.0.0.1 --port 8000
```

Once running, the following endpoints are available:
- **Analyst Web Dashboard**: [http://127.0.0.1:8000/ui/index.html](http://127.0.0.1:8000/ui/index.html)
- **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **OpenAPI JSON Specification**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- **Health Check & Telemetry**: [http://127.0.0.1:8000/v1/health](http://127.0.0.1:8000/v1/health)

### Key REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/v1/gate` | Upload-time profile image safety gate evaluation |
| `POST` | `/v1/evaluate` | Multi-signal actor risk scoring with multi-family gating |
| `POST` | `/v1/graph/cluster` | Graph construction and Louvain community detection |
| `POST` | `/v1/queue/links` | Link verification hold-and-verify queue processing |
| `POST` | `/v1/review/reveal` | Analyst image un-blur with session reveal quota cap (10 max) |
| `GET` | `/v1/policies` | Active policy packs, invariant rules, and thresholds |
| `GET` | `/v1/health` | Service health status and version info |
| `GET` | `/v1/metrics` | Prometheus-compatible signal and telemetry counters |

---

## 6. Python SDK Integration Guide

Platforms can integrate SafeFlow directly using the Python SDK client (`safeflow.sdk.client.SafeFlowClient`).

### Step 1: Initialize the Client

```python
from safeflow.sdk.client import SafeFlowClient

client = SafeFlowClient(base_url="http://127.0.0.1:8000")
```

### Step 2: Gate Profile Avatar Uploads

```python
with open("avatar.png", "rb") as f:
    image_bytes = f.read()

gate_result = client.gate_image(
    image_bytes=image_bytes,
    filename="avatar.png",
    policy_pack="general_video_platform",
    role="creator",
)

if gate_result.decision == "BLOCK":
    print("Upload rejected:", gate_result.message)
elif gate_result.decision == "REVIEW":
    print("Held for triage:", gate_result.message)
else:
    print("Approved:", gate_result.message)
```

### Step 3: Evaluate Multi-Signal Actor Risk

```python
signals = [
    {
        "family": "PROFILE_CHANGE",
        "name": "profile_bio_callout_score",
        "value": 0.85,
        "producer": "profile_plugin",
        "producer_version": "1.0.0",
    },
    {
        "family": "DESTINATION",
        "name": "link_max_dest_risk",
        "value": 0.90,
        "producer": "destination_plugin",
        "producer_version": "1.0.0",
    },
    {
        "family": "TARGETING",
        "name": "targeting_percentile_conc",
        "value": 0.80,
        "producer": "targeting_plugin",
        "producer_version": "1.0.0",
    },
]

decision = client.evaluate_actor(actor_id="actor_987", signals=signals, role="analyst")
print("Risk Level:", decision.level)
print("Risk Score:", decision.score)
print("Action:", decision.recommended_action)
print("Evidence:", decision.evidence)
```

---

## 7. Running Tests & Verifying Invariants

SafeFlow contains **92 automated unit, integration, and property tests** covering every component and architectural boundary.

### Run the Full Test Suite

```bash
pytest tests/ -v
```

### Run Specific Test Modules

```bash
# 1. Profile image safety gate & canary zero-persistence
pytest tests/test_image_gate_pipeline.py -v

# 2. Perceptual hashing robustness bounds (resize, compression, rotation)
pytest tests/test_image_robustness.py -v

# 3. Architectural import boundaries (ensuring core never leaks plugins)
pytest tests/test_import_boundaries.py -v

# 4. Signal plugins suite & popularity discounting
pytest tests/test_signal_plugins.py -v

# 5. Graph construction & Louvain community detection
pytest tests/test_graph_and_clustering.py -v

# 6. Explainable decision engine & signal-family gating
pytest tests/test_decision_engine.py -v

# 7. Evaluation framework, ablations & transfer matrices
pytest tests/test_evaluation_framework.py -v

# 8. Threat simulation lab & link queue tradeoffs
pytest tests/test_threat_simulation_lab.py -v

# 9. REST API & Python SDK
pytest tests/test_api_and_sdk.py -v

# 10. Privacy deletion cascades & research report generator
pytest tests/test_privacy_and_packaging.py -v

# 11. ActivityPub adapter, BK-tree fast indexing & active learning
pytest tests/test_advanced_features.py -v
```

---

## 8. Threat Simulation & Link Queue

The Threat Simulation Lab assesses tradeoff dynamics between attack interception rates and legitimate creator friction:

```bash
safeflow simulate --scenario curiosity_surge --window 30 --samples 100
```

Supported scenarios:
- `curiosity_surge`: Rapid burst of suggestive avatars directing users to bio redirection funnels.
- `cloaked_redirect_evasion`: Multi-step redirect chains hiding behind link shorteners.
- `dormant_hijack_burst`: Aged dormant accounts suddenly activated for mass link dissemination.

### Simulated Clock Verification Windows

| Review Window | Attack Interception Rate | Legitimate Creator Delay | Delayed Activation Intercept | Recommendation |
|---|---|---|---|---|
| **5 min** | 35.00% | 7.50% | 0.00% | Too short for cloaked activations |
| **15 min** | 55.00% | 3.75% | 40.00% | Catches early redirect flips |
| **30 min** | **100.00%** | **3.75%** | **100.00%** | **Recommended Sweet Spot** |
| **60 min** | 100.00% | 3.75% | 100.00% | High security, negligible creator friction |
| **120 min** | 100.00% | 7.50% | 100.00% | Excessive hold delay |

---

## 9. Platform Adapters & Custom Integrations

SafeFlow provides built-in reference adapters for:
1. `video_comments` (YouTube-like video comments and channel headers).
2. `forum_communities` (Reddit-like sub-communities and threaded submissions).
3. `chat_servers` (Discord-like guild channels and high-velocity messages).
4. `activitypub_fediverse` (W3C ActivityPub / Mastodon Notes and Actor profiles).

### Writing a Custom Adapter

Implement the `PlatformAdapter` protocol in `safeflow/adapters/base.py`:

```python
from safeflow.core.schema import Actor, Content, ContentKind, Space, SpaceKind, PopularityMetric, AudienceContext

class MyCustomAdapter:
    @property
    def platform_id(self) -> str:
        return "my_platform"

    def ingest(self, raw_payload: dict) -> dict:
        actor = Actor(
            actor_id=f"act_{raw_payload['user_id']}",
            platform_id=self.platform_id,
            display_name_hash=raw_payload['name_hash'],
        )
        space = Space(
            space_id=f"sp_{raw_payload['room_id']}",
            kind=SpaceKind.CHANNEL,
            popularity=PopularityMetric(raw_count=50, percentile=40.0),
            audience_context=AudienceContext.GENERAL,
        )
        content = Content(
            content_id=f"cnt_{raw_payload['msg_id']}",
            actor_id=actor.actor_id,
            space_id=space.space_id,
            kind=ContentKind.COMMENT,
            text=raw_payload['body'],
        )
        return {"actors": [actor], "spaces": [space], "contents": [content], "links": [], "media": []}
```

---

## 10. Defensive Browser Extension

SafeFlow includes a prototype client-side WebExtension (`extensions/browser/`) that intercepts high-risk redirection funnels in the browser:

### Installation
1. Open Chrome/Edge and navigate to `chrome://extensions/` (or `edge://extensions/`).
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select `extensions/browser/`.
4. The **SafeFlow Shield** icon will appear in your toolbar.

---

## 11. Privacy & GDPR Operations

SafeFlow implements automated GDPR/CCPA data minimization and right-to-be-forgotten controls:

### Exporting Subject Data (GDPR Access Request)

```bash
safeflow data export --actor actor_12345
```
Returns a structured JSON payload of all media hashes, review queue tickets, and appeal records associated with the subject.

### Executing Right-to-be-Forgotten Deletion Cascade

```bash
safeflow data delete --actor actor_12345
```
Irreversibly deletes all stored perceptual hashes, moderation tickets, and appeals for the actor, while logging a privacy-preserving cryptographic hash in the tamper-evident audit log.

---

## 12. Troubleshooting & FAQ

### Q: Why did an image upload return `ALLOW_TAGGED` instead of `BLOCK`?
**A:** Under policy packs like `general_video_platform`, suggestive presentations that do not contain explicit nudity are tagged internally (with a 30-day TTL) rather than blocked. This prevents false-positive over-blocking of benign creators while enabling downstream cross-signal correlation if the actor later disseminates external redirection links.

### Q: Can a single suggestive avatar tag trigger an account suspension?
**A:** **No.** SafeFlow strictly enforces a **single-signal protection invariant**. An isolated suggestive image tag or AI score alone is mathematically capped at `LOW` risk. Elevating to `HIGH` risk requires at least 3 distinct signal families (e.g., Image Tag + Bio Link Callout + High-Space Concentration).

### Q: How do I change the default SQLite database path?
**A:** Supply the `--db` flag in CLI commands, or set the database URL when initializing `DatabaseManager(db_url="sqlite:///my_db.sqlite")` or in production PostgreSQL: `postgresql+psycopg2://user:pass@host/dbname`.

### Q: How do I verify hash chain integrity in the audit log?
**A:** `safeflow.core.audit.AuditLogger.verify_chain(records)` mathematically recomputes the SHA-256 hash chains across all records from the genesis hash to verify that zero entries have been tampered with or deleted.
