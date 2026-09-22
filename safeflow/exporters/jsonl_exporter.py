"""Streaming JSONL Event Exporter for SafeFlow Decisions and Signals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence
from safeflow.core.schema import Decision, Signal


class JSONLEventExporter:
    """Exports decisions and signals as NDJSON/JSONL streams."""

    @classmethod
    def export_decisions(cls, decisions: Sequence[Decision], target_file: str | Path) -> int:
        """Write a sequence of Decision objects to a JSONL file."""
        target_path = Path(target_file)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(target_path, "a", encoding="utf-8") as f:
            for d in decisions:
                f.write(d.model_dump_json() + "\n")
                count += 1
        return count

    @classmethod
    def export_signals(cls, signals: Sequence[Signal], target_file: str | Path) -> int:
        """Write a sequence of Signal objects to a JSONL file."""
        target_path = Path(target_file)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(target_path, "a", encoding="utf-8") as f:
            for s in signals:
                f.write(s.model_dump_json() + "\n")
                count += 1
        return count
