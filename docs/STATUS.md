# SafeFlow Project Status & Gate Verification Checklist

This living document tracks milestone completion, test results, and pre-registered gate verification outputs.

---

## Milestone Progress Summary

- [x] **Milestone 0: Foundations, Governance & Architecture** (Gate 0: PASSED)
- [x] **Milestone 1: Core Skeleton & Profile Image Safety Gate** (Gate 1: PASSED)
- [x] **Milestone 2: Synthetic Generator & Platform Profiles** (Gate 2: PASSED)
- [ ] **Milestone 3: Signal Plugins Suite** (Gate 3: PENDING)
- [ ] **Milestone 4: Graph & Clustering Engine** (Gate 4: PENDING)
- [ ] **Milestone 5: Explainable Decision Engine** (Gate 5: PENDING)
- [ ] **Milestone 6: Evaluation Framework & Ablations** (Gate 6: PENDING)
- [ ] **Milestone 7: Threat Simulation Lab & Link Verification Queue** (Gate 7: PENDING)
- [ ] **Milestone 8: REST API, SDK, Exporters & Dashboard** (Gate 8: PENDING)
- [ ] **Milestone 9: Privacy Controls, Reports & Packaging** (Gate 9: PENDING)

---

## Gate 1 Pre-Registered Specifications

### 1. Pre-Registered Expected CLI Outputs (Amendment 14)

Before running CLI verification commands, their exact expected behaviors and output structures are pre-registered below:

#### Command 1: Analyst Role on Suggestive Image under `general_video_platform`
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role analyst
```
- **Pre-Registered Expected Output**:
  - `Decision`: `ALLOW_TAGGED`
  - `Action`: Image published, internal tag `suggestive_presentation` attached to media record with 30-day TTL.
  - `Visibility`: Analyst role displays full breakdown: `nudity_score` ~ 0.05, `suggestive_score` ~ 0.75, `crop_used`, `model_name="mock_classifier"`, `reasons=["elevated_suggestive_presentation"]`.

#### Command 2: Analyst Role on Suggestive Image under `youth_oriented_service`
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack youth_oriented_service --role analyst
```
- **Pre-Registered Expected Output**:
  - `Decision`: `REVIEW`
  - `Action`: Default placeholder avatar served; image routed to `ReviewBlobStore` with server-side blur; analyst triage ticket created.
  - `Visibility`: Full analyst scores and policy reasoning displayed.

#### Command 3: Creator Role on Suggestive Image under `general_video_platform`
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role creator
```
- **Pre-Registered Expected Output**:
  - `Status`: `ACCEPTED`
  - `Message`: "Your profile image has been approved and published."
  - `Redaction`: Zero internal scores, zero tags, zero model identifiers, zero reasons.

#### Command 4: Creator Role on Explicit Image under Any Pack
```bash
safeflow gate --file tests/fixtures/procedural_avatars/test_explicit.png --pack general_video_platform --role creator
```
- **Pre-Registered Expected Output**:
  - `Status`: `REJECTED`
  - `Message`: "The uploaded image does not meet community guidelines."
  - `Redaction`: Zero internal scores, zero tags; image bytes discarded immediately (zero persistence verified).

---

### 2. Pre-Registered Robustness & Hamming-Distance Table (Amendment 6)

Perceptual hash distances ($64$-bit dHash, wHash, and pHash) evaluated against procedural test avatars across transformations:

| Transformation | Parameters | Evaluated Hash Algorithm | Expected Hamming Bound | Expected Gate Decision |
|---|---|---|---|---|
| **Identity** | Clean re-encode | dHash, wHash, pHash | $0$ | Identical (`ALLOW_TAGGED`) |
| **Resize** | $512\times 512 \to 128\times 128$ | dHash, wHash (pHash) | dHash $\le 1$, wHash $\le 1$, pHash $\le 10$ | Identical (`ALLOW_TAGGED`) |
| **JPEG Re-compression** | Quality factor $60$ | dHash, wHash (pHash) | dHash $\le 1$, wHash $\le 1$, pHash $\le 14$ | Identical (`ALLOW_TAGGED`) |
| **Brightness Perturbation** | $\pm 15\%$ luminance shift | dHash, wHash (pHash) | dHash $\le 1$, wHash $\le 1$, pHash $\le 14$ | Identical (`ALLOW_TAGGED`) |
| **Screenshot Re-encode** | Contrast + JPEG 85 | dHash, wHash (pHash) | dHash $\le 1$, wHash $\le 1$, pHash $\le 10$ | Identical (`ALLOW_TAGGED`) |
| **Subtle Rotation** | $\le 3^\circ$ planar rotation | dHash, wHash (pHash) | dHash $\le 5$, wHash $\le 6$, pHash $\le 12$ | Identical (`ALLOW_TAGGED`) |
| **Slight Crop / Padding** | $5\%$ margin crop | dHash, wHash (pHash) | dHash $\le 18$, wHash $\le 18$, pHash $\le 32$ | Identical (`ALLOW_TAGGED`) |
| **Horizontal Mirror / Flip** | Left-Right reflection | Indexed `mirror_phash` | $0$ (against mirror index) | Identical (`ALLOW_TAGGED`) |
| **Heavy Center Crop (Non-Match)** | $50\%$ center crop | dHash, pHash | $\ge 14$ (Known non-match) | Evaluates center region only |
| **Large Rotation (Non-Match)** | $90^\circ$ rotation | dHash, pHash | $\ge 16$ (Known non-match) | Evaluates rotated geometry |

*Rule: Thresholds are recorded based on mathematical properties of DCT frequency grids and gradient differences. Known non-matches (heavy crop, $90^\circ$ rotation) are documented as inherent mathematical properties.*

---

## Gate 1 Checklist (VERIFIED & PASSED)

- [x] Import-boundary test passes (`safeflow.core` imports zero plugins/adapters; plugins do not import each other).
- [x] Procedural avatar generator produces valid geometric avatars with non-depictive pre-strip metadata and pixel markers.
- [x] Zero blocked image persistence verified by canary byte scan across DB, temp files, and logs.
- [x] Perceptual hashes calculated for BLOCK before discarding image bytes.
- [x] Generic role redaction strips internal scores/tags for creator role.
- [x] ReviewBlobStore encrypted in-memory storage, auto-purge TTL, server-side blur, and session reveal caps verified.
- [x] Host-provided `MediaFetcher` protocol and `RescanRequest` events verified with fixture fetcher.
- [x] Policy pack loader enforces non-overridable invariants and rejects adversarial packs.
- [x] Dual-crop evaluation selects higher risk crop between full image and circular avatar crop.
- [x] Tamper-evident audit log verifies hash-chain integrity.
- [x] All pytest suites pass cleanly (`pytest -v`: 33 passed in 5.02s).
- [x] `safeflow gate` CLI demonstrates pre-registered outputs exactly.
- [x] Milestone 1 committed to git.

---

## Gate 2 Checklist: Synthetic Generator & Platform Profiles (VERIFIED & PASSED)

- [x] **Determinism Test**: Generator is 100% deterministic (identical seed produces byte-identical JSONL exports and matching file SHA-256 checksums).
- [x] **Variant A vs Variant B Separation**: Variant B exhibits shifted comment lexicons and distinct temporal cluster variations.
- [x] **Three Platform Profiles**: `video_comments` (YouTube-like), `forum_communities` (Reddit-like), `chat_servers` (Discord-like) implemented with distinct topologies, timing models, and vocabularies.
- [x] **Canonical Schema Validation**: `safeflow validate-dataset` passes 100% compliance against canonical schemas on all 3 profiles.
- [x] **10 Attack Categories Synthesized**: `SPAM`, `CURIOSITY_FUNNEL`, `AI_IMAGE_NETWORK`, `IMAGE_REUSE_NETWORK`, `LINK_ABUSE`, `ACCOUNT_ROTATION`, `MIXED_ATTACK`, `HIJACKED_ACCOUNT`, `AGED_ACCOUNT_ATTACK`, `HUMAN_FARM`.
- [x] **6 Legitimate Categories Synthesized**: `NORMAL`, `NORMAL_HIGH_ENGAGEMENT`, `LEGIT_FANDOM`, `LEGIT_AVATAR_REUSE`, `LEGIT_LINK_CREATOR`, `LEGIT_SUGGESTIVE_AVATAR`.
- [x] **Strict Zero Depictive/Scraped Image Compliance**: 100% of media records are procedural placeholders with perceptual hashes.
- [x] **Mock Destinations**: All external destinations are mock `*.local` domains with redirect chains, shorteners, cloaking, and activation delay.
- [x] **CLI Commands**: `safeflow generate` and `safeflow validate-dataset` operational.
- [x] **Full Regression Suite**: 44/44 pytest tests pass cleanly in 36s.

