"""Validator for generic JSONL data files against canonical schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from safeflow.core.schema import (
    Actor,
    Content,
    Decision,
    Link,
    Media,
    Relation,
    Signal,
    Space,
)

ENTITY_TYPE_MAP = {
    "actor": Actor,
    "space": Space,
    "content": Content,
    "media": Media,
    "link": Link,
    "relation": Relation,
    "signal": Signal,
    "decision": Decision,
}


class JSONLValidationError(Exception):
    pass


class GenericJSONLValidator:
    """Validates records in JSONL files against canonical SafeFlow schemas."""

    @classmethod
    def validate_file(cls, path: str | Path) -> dict[str, int]:
        """Validate a JSONL file line-by-line. Returns counts per entity type."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"JSONL file not found: {file_path}")

        counts: dict[str, int] = {k: 0 for k in ENTITY_TYPE_MAP}
        with open(file_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    record = json.loads(clean_line)
                except Exception as e:
                    raise JSONLValidationError(f"Line {line_no}: Invalid JSON: {e}") from e

                entity_type = record.get("entity_type")
                if not entity_type or entity_type not in ENTITY_TYPE_MAP:
                    raise JSONLValidationError(
                        f"Line {line_no}: Missing or unrecognized 'entity_type': '{entity_type}'"
                    )

                model_cls = ENTITY_TYPE_MAP[entity_type]
                try:
                    # Strip the envelope entity_type before validating model
                    payload = {k: v for k, v in record.items() if k != "entity_type"}
                    model_cls.model_validate(payload)
                    counts[entity_type] += 1
                except Exception as e:
                    raise JSONLValidationError(
                        f"Line {line_no}: Validation failure for '{entity_type}': {e}"
                    ) from e

        return counts
