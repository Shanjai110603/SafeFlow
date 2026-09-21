# SafeFlow

**An open, platform-agnostic trust & safety signal and decision engine.**

SafeFlow provides reusable detection components (profile-image safety gate, media-reuse linking, behavior and coordination analysis, link/destination analysis) plus an explainable decision engine, for detecting coordinated pathways that lead users toward age-inappropriate destinations. Any platform can integrate SafeFlow through a thin adapter.

> [!IMPORTANT]
> **Non-Affiliation Notice:** SafeFlow is an independent, defensive research project. It is not affiliated with Google, YouTube, or any other platform, has no access to any platform's internal systems, and must never claim otherwise in code, docs, UI, or reports.

---

## Key Principles

1. **Facts vs. Policy**: Detectors output platform-neutral facts; policy packs define platform-specific actions and thresholds.
2. **Multi-Hop Redirection Pathway Analysis**: Connects attention surface signals (comments/posts) to identity surfaces (avatars/bios) and external destinations.
3. **Hard Safety & Zero-Harm Rules**:
   - Zero explicit imagery generated, scraped, or stored.
   - All test avatars are procedurally generated geometric placeholders.
   - Blocked images are never persisted in databases, filesystem, or logs.
   - CSAM: strict stop-and-report protocol (see `docs/RESPONSIBLE_RESEARCH.md`).
   - Humans in the loop: risk scores produce analyst recommendations, not unilateral automated punishments.

---

## Documentation

- [Architecture & Topology](docs/ARCHITECTURE.md)
- [Milestone Roadmap & Plan](docs/PLAN.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Responsible Research Protocol](docs/RESPONSIBLE_RESEARCH.md)
- [Intended Use & Misuse Posture](docs/INTENDED_USE.md)
- [Prior Art & Dependency Licenses](docs/PRIOR_ART.md)
- [Architectural Decision Records](docs/DECISIONS.md)
- [Image Safety Policy](docs/IMAGE_POLICY.md)
- [Status & Verification Checklist](docs/STATUS.md)

---

## Quickstart (Development)

```bash
# Clone and install in editable mode
git clone https://github.com/SafeFlow/safeflow.git
cd safeflow
pip install -e ".[dev]"

# Run upload-time image safety gate CLI
python -m safeflow.cli.main gate --file tests/fixtures/procedural_avatars/test_suggestive.png --pack general_video_platform --role analyst

# Run verification test suite
pytest tests/ -v
```

---

## License

SafeFlow is proposed under the [Apache-2.0 License](LICENSE), subject to our ethical research commitments.
