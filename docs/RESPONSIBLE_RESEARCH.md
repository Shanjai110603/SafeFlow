# SafeFlow Responsible Research & Zero-Harm Protocol

SafeFlow is an independent, defensive trust & safety research project. It is not affiliated with Google, YouTube, or any other platform, has no access to any commercial platform's internal systems, and makes no claim of endorsement or partnership.

This document establishes the **binding ethical and legal boundaries** governing this project. These rules are absolute and must never be bypassed, altered, or weakened in code, tests, documentation, or operational research.

---

## 1. Absolute Ethical & Legal Rules

### 1. Zero Explicit Imagery Rule
- **No Generation, Scraping, Sourcing, or Storage**: Under no circumstances does this repository generate, scrape, download, source, or persist nudity, sexually explicit, or sexualized imagery of any individual.
- **Procedural Placeholders Only**: All test avatars and media fixtures in this repository are **procedurally generated placeholders** consisting of geometric shapes, color gradients, letter initials, and mathematical patterns.
- **Metadata-Only Ground Truth**: Ground-truth labels (such as `NUDITY`, `EXPLICIT`, `SUGGESTIVE`, `AMBIGUOUS`, or `NEUTRAL`) exist strictly in non-depictive image metadata (PNG `tEXt` chunks or sidecar JSON) to drive mock classifiers.

### 2. No Model Training on Explicit Content
- SafeFlow does not train, fine-tune, or calibrate any machine learning model on explicit or sexualized imagery. Pretrained models, if evaluated, run strictly behind abstracted interfaces as optional third-party extras.

### 3. Zero Age Estimation & Minor Protection
- **No Biometric Age Estimation**: SafeFlow does not perform age estimation, facial analysis, or developmental classification on people depicted in media.
- **No Profiling of Minors**: SafeFlow does not attempt to identify, label, or profile minor users.
- **Space Metadata as Proxy**: "Audience exposure risk" is evaluated solely using platform-configured or synthetic space-level metadata (e.g., whether a forum or video is tagged as general, mixed, or youth-oriented).

### 4. CSAM Strict Non-Engagement & Stop-and-Report Protocol
- **No CSAM Detection Models**: SafeFlow does not build, train, or evaluate child sexual abuse material (CSAM) detection algorithms.
- **Authorized Hash Matching Simulation**: Matching against known abusive material belongs strictly to hash lists maintained by authorized statutory bodies (such as NCMEC or the Internet Watch Foundation). The SafeFlow MVP simulates this process using a synthetic, benign mock hash list.
- **Mandatory Stop-and-Report Rule**:
  > **STOP-AND-REPORT PROTOCOL:**
  > If any researcher, engineer, or system operator using or developing SafeFlow encounters suspected Child Sexual Abuse Material (CSAM) or Child Sexual Exploitation and Abuse (CSAE):
  > 1. **STOP IMMEDIATELY.** Do not attempt to process, classify, download, scrape, screenshot, or re-encode the material.
  > 2. **DO NOT RETAIN OR SHARE.** Do not save the image to disk, cache, database, or test fixtures. Do not transmit it over internal chats or bug reports.
  > 3. **REPORT TO STATUTORY AUTHORITIES IMMEDIATELY**:
  >    - **International / US**: National Center for Missing & Exploited Children (NCMEC) via [report.cybertip.org](https://report.cybertip.org).
  >    - **International / UK**: Internet Watch Foundation (IWF) via [report.iwf.org.uk](https://report.iwf.org.uk).
  >    - **India**: National Cyber Crime Reporting Portal at [cybercrime.gov.in](https://cybercrime.gov.in) and National Commission for Protection of Child Rights (NCPCR) emergency channels.

### 5. No Real Likenesses or Personal Photos
- No photographs of real individuals, public figures, or scraped social media avatars may be stored or processed in this project.

### 6. No Live Seeding & No Platform Scraping
- SafeFlow code must never post comments, create accounts, seed synthetic traffic, or interact with any live platform.
- SafeFlow must never bypass authentication, CAPTCHAs, rate limits, anti-bot mechanisms, or private platform APIs.
- The MVP operates exclusively on synthetic and local datasets. Real-platform adapters are disabled interface stubs requiring explicit API keys, compliance reviews (GDPR, India DPDP Act), and compliance with official platform Terms of Service.

### 7. No Crawling of Real Adult Websites
- All target destinations in test scenarios are simulated mock hosts ending in `.local` with synthetic metadata. No HTTP requests are ever issued to actual adult or commercial sites.

### 8. Immediate Zero-Byte Purge of Blocked Media
- Uploaded media receiving a `BLOCK` decision is immediately discarded from memory. No image bytes are ever written to database tables, filesystem directories, temporary files, or logs. Only the perceptual hash, decision string, model version, thresholds, and timestamp are preserved.

### 9. No Cross-Platform Identity Linking
- SafeFlow does not attempt to identify individuals across platform boundaries. The engine operates on pseudonymized identifiers (salted HMACs) scoped to a single platform tenant.

### 10. Human-in-the-Loop: No Automated Actor Punishment
- The core decision engine produces **recommendations for human review** (e.g., "route to queue", "request manual audit").
- SafeFlow core does not execute automated punitive actions (such as automated account banning or deletion) on actors. The only automated gate action is upload-time media gating (`BLOCK`/`HOLD`), which is fully reversible via human appeal.

---

## 2. Objective, Non-Prejudicial Language Standards

Trust & Safety systems must avoid circular or moralizing assertions. SafeFlow enforces strict language conventions across code, logs, and explanations:
- **Prohibited**: "This person is malicious", "Bad actor detected", "Fraudster account".
- **Required**: "This account exhibits $N$ signals associated with the simulated abuse pattern."
- **Policy Calibration**: All numerical thresholds provided in configs are explicitly identified as **uncalibrated research placeholders**, never production dogma.
