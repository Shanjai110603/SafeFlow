# SafeFlow Architectural Decision Records (ADR)

This running log documents every significant technical, architectural, and ethical judgment call made in SafeFlow.

---

### ADR-001: Canonical Schema Specification via Pydantic v2
- **Context**: Platforms have vastly different data representations (YouTube comments vs Reddit posts vs Discord messages).
- **Decision**: Define a single platform-agnostic canonical schema (`Actor`, `Space`, `Content`, `Media`, `Link`, `Relation`, `Signal`, `Decision`) using Pydantic v2 with an explicit `schema_version = "1.0.0"`. Export JSON Schemas via CLI to facilitate validation in non-Python environments.
- **Consequences**: Thin adapters map native platform schemas into canonical entities; core logic remains completely isolated from platform quirks.

---

### ADR-002: Persistence Engine Selection (SQLAlchemy 2 + SQLite Default)
- **Context**: The system requires storage for media hashes, audit logs, review queues, and appeals. Complex external graph databases (e.g., Neo4j) or separate database clusters increase installation friction.
- **Decision**: Use SQLAlchemy 2 with a default local SQLite engine (and optional PostgreSQL connection string support via configuration). Use in-memory NetworkX for graph analytics.
- **Consequences**: SafeFlow installs and executes seamlessly from CLI/pytest with zero external database dependencies.

---

### ADR-003: Pluggable Signal Architecture with Strict Boundary Enforcement
- **Context**: Signal detectors must be modular, swappable, and extensible by external contributors.
- **Decision**: Implement a `SignalPlugin` Python protocol. Core never imports plugin implementations. Plugins import only canonical schema and core protocols. Plugins never import each other.
- **Consequences**: Image safety, behavioral analysis, and destination inspection operate as self-contained plugins.

---

### ADR-004: Proposed Licensing Strategy
- **Context**: Open-source defensive trust & safety software requires an appropriate balance between commercial platform adoption and ethical usage constraints.
- **Decision**: Propose the **Apache License 2.0** combined with a prominent `RESPONSIBLE_USE.md` ethical statement. Final decision reserved for the project maintainer.
- **Consequences**: Ensures compatibility with enterprise and open-source platform stacks without copyleft restrictions, while stating clear zero-harm expectations.

---

### ADR-005: Generic Field-Level Role Redaction
- **Context**: Creator-facing responses must not leak internal scores, model names, or classifier reasons, but core must not hardcode plugin-specific output classes.
- **Decision**: Plugins declare field-level visibility on Pydantic models using `Field(..., json_schema_extra={"visibility": "analyst"})`. Core provides a generic `RoleRedactor` that filters models dynamically based on the caller's role (`CREATOR`, `ANALYST`, `ADMIN`).
- **Consequences**: Core remains completely decoupled from plugin schemas while guaranteeing strict redaction.

---

### ADR-006: ReviewBlobStore with Encrypted In-Memory Storage & Auto-Purge
- **Context**: Media flagged for human review (`REVIEW`) must be inspectable by analysts, but keeping unencrypted raw images on disk violates data minimization and safety principles.
- **Decision**: Implement `ReviewBlobStore` supporting encrypted in-memory storage (or AES-GCM at rest), automatic TTL purge based on review SLA, server-side Gaussian blurred previews by default, logged reveals, and per-analyst session reveal caps.
- **Consequences**: Protects human analysts from unneeded exposure to shocking imagery, prevents accidental disk retention, and complies with data minimization laws.

---

### ADR-007: Perceptual Hashing for BLOCK Before Zero-Byte Discard
- **Context**: Blocked images must never be persisted, but the system must remember the perceptual hash to detect repeated uploads and link coordinated campaigns.
- **Decision**: Compute perceptual hashes (pHash, dHash, wHash) in memory *before* releasing image byte buffers. Once hashes and metadata are logged to the database, image bytes are immediately deallocated.
- **Consequences**: Satisfies both the zero-byte persistence mandate and media reuse detection requirements.

---

### ADR-008: Non-Overridable Policy Pack Invariants
- **Context**: Platform operators customize policy packs (e.g., adult platform vs youth service). Permitting arbitrary overrides could accidentally or maliciously disable vital safety guardrails.
- **Decision**: The policy pack loader enforces non-overridable invariants:
  1. Known-bad hash matching cannot be disabled.
  2. Fail-closed behavior on classifier errors cannot be disabled.
  3. Creator role redaction cannot be disabled.
  4. Blocked image persistence cannot be enabled.
  Any policy pack attempting to violate these invariants is rejected at load time.
- **Consequences**: Hard safety and legal rules cannot be undermined by policy configurations.

---

### ADR-009: Upload Security Hardening & Memory-Only Processing
- **Context**: Uploaded avatars are untrusted inputs vulnerable to image decompression bombs, malicious SVG execution, or EXIF exploits.
- **Decision**:
  1. Restrict allowed formats to PNG, JPEG, and WebP (SVG is strictly rejected).
  2. Enforce a pixel limit cap (`Image.MAX_IMAGE_PIXELS = 25_000_000`) before decoding.
  3. Apply EXIF orientation via `ImageOps.exif_transpose` before stripping all metadata.
  4. Process all streams strictly in-memory using `io.BytesIO`; never write raw uploads to temporary disk files.
- **Consequences**: Prevents server denial-of-service, remote code execution, and metadata leaks.

---

### ADR-010: Procedural Avatar Dual-Crop Evaluation & Non-Depictive Pixel Markers
- **Context**: Procedural avatars must reliably simulate scenarios where the full image is neutral while a circular avatar display crop contains a flagged region (or vice versa), without depicting explicit imagery.
- **Decision**: Procedural avatars encode ground truth in pre-strip PNG metadata and optionally include non-depictive, geometric pixel marker regions (e.g., patterned corner tiles outside the crop vs center tiles within the crop). The `MockClassifier` evaluates both the full image and a circular crop, picking the maximum risk score.
- **Consequences**: Robustly tests dual-crop logic across resize, JPEG compression, and mirroring without generating inappropriate imagery.

---

### ADR-011: Cryptographic Hash-Chained Audit Trail
- **Context**: Audit logs for moderation decisions and analyst inspections must be tamper-evident.
- **Decision**: Audit records link to their predecessor via SHA-256 hash-chaining ($\text{Hash}_i = \text{SHA256}(\text{Hash}_{i-1} \parallel \text{Timestamp} \parallel \text{Payload})$).
- **Consequences**: Any unauthorized modification or deletion of audit logs is mathematically detectable.
