# SafeFlow Prior Art & Dependency Licensing Analysis

This document catalogs existing systems, libraries, algorithms, and academic literature relevant to SafeFlow. Every license documented below has been **empirically verified from the upstream package registry or primary repository**, not recalled from memory.

---

## 1. Image Safety Classifiers & Detection Backends

| Project / Component | Role in SafeFlow | Verified License | Dependency Status | Notes & Legal Risk Analysis |
|---|---|---|---|---|
| **`bhky/opennsfw2`** | Whole-image NSFW probability baseline. | **MIT** (weights Yahoo BSD-2-Clause) | **Optional Extra** (behind interface) | Low risk. Permissive license. Operates via PyTorch/Keras to produce a single continuous score $[0, 1]$. |
| **`notAI-tech/NudeNet`** | Body-part detector distinguishing exposed vs covered regions. | **GNU AGPL-3.0** (due to Ultralytics YOLOv8 upstream) | **Optional Extra** (behind interface only; never in core) | **CRITICAL LICENSE CONFLICT**: While early v1 releases claimed MIT, modern NudeNet is built upon Ultralytics YOLO, which enforces AGPL-3.0. Distributing NudeNet as a direct dependency would impose viral copyleft obligations on SafeFlow or any platform embedding it. SafeFlow isolates NudeNet behind an external protocol stub and does not install it in core. |
| **`Falconsai/nsfw_image_detection`** | Vision Transformer (ViT) whole-image moderation classifier on Hugging Face. | **Apache-2.0** | **Optional Extra** | Permissive license. Useful as an alternative whole-image classifier. |
| **`arritgashi/nudity-detector`** | Self-hosted ensemble combining body-part detection with whole-image classification into ALLOW/REVIEW/BLOCK. | **MIT** (wrapper code; notes upstream weights retain native licenses) | **Inspiration Only** | Studied for tiering logic (body-part + whole-image combination). SafeFlow implements its own configurable ensemble logic and evaluates performance independently. |
| **Commercial APIs** (Sightengine, Hive, AWS Rekognition) | Benchmarks and external adapters. | Proprietary (API Terms of Service) | **Disabled Stubs Only** | Off by default. Explicit warning: using commercial APIs transmits user image bytes to third parties, triggering GDPR and DPDP compliance obligations. |

---

## 2. Media Reuse & Perceptual Hashing

| Project / Component | Role in SafeFlow | Verified License | Dependency Status | Notes |
|---|---|---|---|---|
| **`imagehash`** | Multi-algorithm perceptual hashing (pHash, dHash, wHash) for avatar reuse. | **BSD 2-Clause** | **Core Dependency** | Permissive license. Fast, pure-Python/NumPy/SciPy implementation. Computes 64-bit perceptual hashes. |
| **Meta PDQ** (`facebook/ThreatExchange`) | Industry-standard 256-bit perceptual hash with dihedral invariance. | **BSD 3-Clause** | **Optional Extra** | Evaluated as an alternative to `imagehash` for large-scale enterprise deployments. |
| **FAISS** (Meta) | High-performance vector and Hamming similarity indexing. | **MIT** | **Future Scaling Note** | Not included in MVP. Documented as an enterprise scaling path for millions of daily perceptual hashes. |

---

## 3. Coordinated Behavior & Network Analysis

| Literature / Project | Role in SafeFlow | License / Source | Dependency Status | Key Takeaways & Controls |
|---|---|---|---|---|
| **YouTube RCAT** (Reverse Common Attention Testing) | Engagement-fraud detection using bipartite co-visit graphs and statistical risk ratios. | Academic Publication (Google / YouTube Research) | **Inspiration Only** | **Key Concepts Borrowed**: Bipartite projection of actors onto spaces; measuring co-targeting overlap against expected random chance.<br>**Critical Warning Adopted**: RCAT explicitly cautions that false positives increase sharply as group size grows. SafeFlow enforces the rule that co-visit overlap must never be used alone to punish individuals. |
| **CooRnet** | Coordinated sharing behavior detection via rapid co-sharing intervals. | Academic Paper / R Package (GPL-3) | **Inspiration Only** | Philosophy of time-windowed co-action. No code copied. |
| **Roblox Sentinel** (`Roblox/Sentinel`) | Temporal trajectory modeling: contrastive learning over conversation history to detect rare risk patterns early. | **Apache-2.0** | **Inspiration Only** | **Philosophy Borrowed**: "Detect the pattern over time, not the single message." SafeFlow adopts this for temporal trajectory features across multi-hop surfaces. SafeFlow does **not** perform grooming detection. |
| **Unverified Repositories** (`sentinel-safety/SENTINEL`) | Investigated during prior art review. | Unverified / Inaccessible | **Rejected** | Per project rules, SafeFlow never depends upon or references unverified repositories. |

---

## 4. Open Trust & Safety Infrastructure

| Project | Role in SafeFlow | Verified License | Dependency Status | Notes |
|---|---|---|---|---|
| **ROOST Coop** (`roostorg/coop`) | Open-source human moderation review console. | **Apache-2.0** | **Export Compatibility** | SafeFlow does not replicate an enterprise review console. SafeFlow provides a minimal demo queue and standard export interfaces (JSONL, webhook) compatible with Coop ingestion formats. |
| **ROOST / Discord Osprey** (`roostorg/osprey`) | Real-time event-driven rules engine. | **Apache-2.0** | **Export Compatibility** | Evaluated for rule syntax and event export schemas. |

---

## 5. Literature Check & Novelty Statement

### Established Prior Art:
- Web spam campaign detection and link-farm analysis (e.g., TrustRank, link graph spectral analysis).
- Coordinated inauthentic behavior (CIB) detection on social networks (e.g., astroturfing, retweet rings).
- Automated content-level moderation (text toxicity classifiers, adult image detectors).

### SafeFlow Novelty:
SafeFlow does not claim to invent link spam detection or image classification. SafeFlow's specific technical contribution is the **integration and evaluation design**:
1. **Multi-Hop Pathway Correlation**: Linking outwardly benign comments on attention surfaces with subtle identity cues and external cloaked destinations.
2. **Platform-Agnostic Portability**: Proving that the exact same core engine operates effectively across video comments, forum communities, and chat servers via thin adapters.
3. **Legitimate-Coordination Controls**: Incorporating explicit popularity discounting and negative controls (`LEGIT_FANDOM`, `LEGIT_AVATAR_REUSE`, `LEGIT_LINK_CREATOR`, `NORMAL_HIGH_ENGAGEMENT`) to minimize false positives against benign community behaviors.
