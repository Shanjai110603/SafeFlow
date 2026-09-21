# SafeFlow Intended Use & Misuse Posture

## 1. Intended Use & Target Users

SafeFlow is designed as an open-source, defensive software library to assist organizations and researchers in analyzing coordinated behavioral patterns and multi-hop traffic funnels.

### Intended Audiences:
- **Trust & Safety Engineering Teams**: To evaluate signal pipelines, integrate multi-hop pathway analysis into review queues, and benchmark defensive policies.
- **Defensive Academic & Safety Researchers**: To study coordinated behavior, link obfuscation techniques, and explainable decision-making architectures.
- **Platform Policy Teams**: To simulate the downstream impacts of different policy configurations prior to production deployment.

SafeFlow is designed around **Human-in-the-Loop (HITL)** operational standards: risk outputs are advisory recommendations for analysts, not unilateral automated punishments.

---

## 2. Explicit Misuse Prohibitions

SafeFlow must not be used, modified, or deployed for any of the following activities:
1. **Surveillance & Individual Tracking**: Attempting to deanonymize, track, or identify specific real-world individuals across platforms or services.
2. **Appearance-Based Person Scoring**: Using visual classification to rate, rank, or score real human individuals, bodies, or likenesses.
3. **Automated Punitive Enforcement**: Deploying automated account-level sanctions (bans, account suspensions, financial penalties) without human analyst review and due process.
4. **Minor Surveillance**: Collecting, analyzing, or processing personal data belonging to known minors.
5. **Discriminatory or Biased Gating**: Enforcing moderation decisions that disproportionately impact protected demographic groups or censor legitimate speech without transparent appeal pathways.

---

## 3. Privacy & Access Tiering

Trust & Safety systems must prevent adversarial reverse-engineering while upholding user privacy. SafeFlow establishes strict visibility tiers:

| Role | Permitted Information | Explicitly Redacted / Forbidden |
|---|---|---|
| **Creator / End-User** | High-level status (`ACCEPTED`, `UNDER_REVIEW`, `REJECTED`), generic user guidance, appeal submission link. | Internal scores, model names, perceptual hash values, evidence reasons, internal tags (`suggestive_presentation`), decision thresholds. |
| **Analyst** | Full explanation object, raw signal values, perceptual hash matches, temporal history, review queue actions. | Real-world personal identity data (identifiers remain pseudonymized). Every tag read is logged to the tamper-evident audit trail. |
| **Administrator** | System metrics, policy pack configurations, audit logs, queue SLAs, plugin health. | Cannot override fundamental safety invariants. |

---

## 4. Adversarial Posture & Research Placeholders

All configurations, thresholds, and ensemble weights bundled with SafeFlow are **uncalibrated research placeholders**.
- They are provided to validate that pipelines function mathematically and logically end-to-end.
- They must **never be assumed to represent an optimal or battle-tested policy** for any live platform.
- Live deployment requires empirical calibration against the platform's specific content distribution, abuse volume, and analyst queue capacity.

---

## 5. Licensing Proposal

We propose licensing the SafeFlow core codebase under the **Apache License 2.0**, supplemented by an explicit **RESPONSIBLE_USE.md** ethics declaration.
- **Why Apache-2.0**: It grants broad permissions for defensive integration and commercial platform adaptation, provides an explicit patent grant, and avoids restrictive copyleft contagions.
- **Governance**: The final licensing decision rests with the project maintainer.
