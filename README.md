# SafeFlow

**An open, platform-agnostic trust & safety signal and decision engine.**

SafeFlow provides modular, multi-modal detection components (profile-image safety gate, media-reuse linking, text behavior analysis, high-space targeting, link/destination analysis) plus an explainable decision engine and graph clustering framework for detecting coordinated pathways that funnel users toward age-inappropriate destinations. Any platform can integrate SafeFlow through a thin adapter.

> [!IMPORTANT]
> **Non-Affiliation Notice:** SafeFlow is an independent, defensive research project. It is not affiliated with Google, YouTube, or any other platform, has no access to any platform's internal systems, and must never claim otherwise in code, docs, UI, or reports.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Attention Surfaces
        A1[Video Comments]
        A2[Community Posts]
        A3[Chat Messages]
    end

    subgraph Signal Extraction Pipeline
        S1[Media Reuse & Perceptual Hash Plugin]
        S2[Text Repetition & Velocity Plugin]
        S3[Targeting & Bipartite Concentration Plugin]
        S4[Link Destination & Cloak Plugin]
        S5[Profile Obfuscation & Bio Plugin]
    end

    subgraph Correlation & Decision
        G[Heterogeneous Graph & Louvain Clustering Engine]
        D[Explainable Decision Engine with Signal-Family Gating]
    end

    subgraph Actions & Triage
        Q[Simulated Clock Hold-and-Verify Queue]
        UI[Analyst Workbench with Gaussian Blur & 10-Reveal Quota]
        EXP[JSONL SIEM & Webhook Dispatchers]
    end

    Attention Surfaces --> Signal Extraction Pipeline
    Signal Extraction Pipeline --> G
    Signal Extraction Pipeline --> D
    G --> D
    D --> Q
    D --> UI
    D --> EXP
```

---

## Core Invariants & Safety Principles

1. **Facts vs. Policy**: Detectors output platform-neutral facts; policy packs define platform-specific actions, thresholds, and role-based views.
2. **Multi-Hop Redirection Pathway Analysis**: Connects attention surface signals (comments/posts) to identity surfaces (avatars/bios) and external destinations.
3. **Hard Safety & Zero-Harm Rules**:
   - **Zero Depictive Imagery**: Strictly zero explicit or scraped imagery. All test avatars are procedurally generated geometric placeholders.
   - **Canary-Scanned Zero Persistence**: Blocked images are immediately purged with zero storage on disk, memory, or database.
   - **No CSAM Scanning**: SafeFlow implements a strict immediate stop-and-report protocol (see [Responsible Research](docs/RESPONSIBLE_RESEARCH.md)).
   - **Analyst Wellbeing**: Server-side Gaussian blur is enabled by default with tamper-evident reveal logging and a 10-reveal session cap.
   - **Privacy Compliance**: Built-in GDPR/CCPA right-to-be-forgotten deletion cascades and structured data export utilities.

---

## Documentation

- [Project Status & Gate Verification](docs/STATUS.md)
- [Research Report](docs/RESEARCH_REPORT.md)
- [Architecture & Topology](docs/ARCHITECTURE.md)
- [Limitations & Scope](docs/LIMITATIONS.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Responsible Research Protocol](docs/RESPONSIBLE_RESEARCH.md)
- [Intended Use & Misuse Posture](docs/INTENDED_USE.md)
- [Prior Art & Dependency Licenses](docs/PRIOR_ART.md)
- [Architectural Decision Records](docs/DECISIONS.md)
- [Image Safety Policy](docs/IMAGE_POLICY.md)

---

## Quickstart

### 1. Installation

```bash
# Clone and install
git clone https://github.com/SafeFlow/safeflow.git
cd SafeFlow
pip install -e ".[dev]"
```

### 2. Interactive Terminal Walkthrough

```bash
python -m safeflow.cli.main demo --profile video_comments
```

### 3. Threat Simulation Sweep

```bash
python -m safeflow.cli.main simulate --scenario curiosity_surge --window 30
```

### 4. Compile Research Report

```bash
python -m safeflow.cli.main report --out docs/RESEARCH_REPORT.md
```

### 5. Launch REST API & Analyst Dashboard

```bash
python -m safeflow.cli.main serve --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/ui/index.html` in your browser to explore the dashboard.

---

## Python SDK Quickstart

```python
from safeflow.sdk.client import SafeFlowClient

client = SafeFlowClient(base_url="http://127.0.0.1:8000")

# 1. Gate an image upload
gate_result = client.gate_image(
    image_bytes=b"...",
    filename="avatar.png",
    policy_pack="general_video_platform",
    role="creator",
)
print("Gate Decision:", gate_result.decision)

# 2. Evaluate actor risk
signals = [
    {"family": "PROFILE_CHANGE", "name": "bio_callout", "value": 0.85, "producer": "profile_plugin"},
    {"family": "DESTINATION", "name": "max_risk", "value": 0.90, "producer": "dest_plugin"},
    {"family": "TARGETING", "name": "popular_concentration", "value": 0.80, "producer": "target_plugin"},
]
decision = client.evaluate_actor(actor_id="actor_123", signals=signals)
print("Actor Risk Level:", decision.level, "Score:", decision.score)
```

---

## Verification & Test Suite

Run the full test suite (88 passing unit, integration, and property tests):

```bash
pytest tests/ -v
```

---

## License

SafeFlow is licensed under the [Apache-2.0 License](LICENSE), subject to our ethical research commitments.

