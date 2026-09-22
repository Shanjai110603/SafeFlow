"""Dataset export utilities for JSONL, SQLite, and manifest.json."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from safeflow.adapters.synthetic.generator import SyntheticDataset


class DatasetExporter:
    """Exports synthetic datasets to disk in canonical JSONL, SQLite, and manifest formats."""

    @classmethod
    def export(cls, dataset: SyntheticDataset, output_dir: str | Path) -> dict[str, Any]:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        entity_counts: dict[str, int] = {
            "actors": len(dataset.actors),
            "spaces": len(dataset.spaces),
            "content": len(dataset.content),
            "media": len(dataset.media),
            "links": len(dataset.links),
            "relations": len(dataset.relations),
        }

        # 1. Export individual JSONL files and unified dataset.jsonl
        unified_file = out_path / "dataset.jsonl"
        with open(unified_file, "w", encoding="utf-8") as u_f:
            # Actors
            cls._write_jsonl(out_path / "actors.jsonl", dataset.actors, "actor", u_f)
            # Spaces
            cls._write_jsonl(out_path / "spaces.jsonl", dataset.spaces, "space", u_f)
            # Content
            cls._write_jsonl(out_path / "content.jsonl", dataset.content, "content", u_f)
            # Media
            cls._write_jsonl(out_path / "media.jsonl", dataset.media, "media", u_f)
            # Links
            cls._write_jsonl(out_path / "links.jsonl", dataset.links, "link", u_f)
            # Relations
            cls._write_jsonl(out_path / "relations.jsonl", dataset.relations, "relation", u_f)

        # 2. Export SQLite database
        db_file = out_path / f"synthetic_{dataset.config.platform_profile}_{dataset.config.variant}.db"
        cls._write_sqlite(db_file, dataset)

        # 3. Compute SHA-256 hashes for all exported files
        file_hashes: dict[str, str] = {}
        for item in sorted(out_path.glob("*.jsonl")):
            file_hashes[item.name] = cls._file_sha256(item)
        if db_file.exists():
            file_hashes[db_file.name] = cls._file_sha256(db_file)

        # 4. Generate manifest.json
        manifest = {
            "generator_version": "1.0.0",
            "seed": dataset.config.seed,
            "variant": dataset.config.variant,
            "platform_profile": dataset.config.platform_profile,
            "base_rate": dataset.config.base_rate,
            "actor_count": dataset.config.actor_count,
            "entity_counts": entity_counts,
            "file_checksums_sha256": file_hashes,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        manifest_file = out_path / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as m_f:
            json.dump(manifest, m_f, indent=2)

        return manifest

    @staticmethod
    def _write_jsonl(path: Path, items: list[Any], entity_type: str, unified_file: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                raw_dict = item.model_dump(mode="json")
                # Specific file writes pure canonical model
                f.write(json.dumps(raw_dict) + "\n")
                # Unified file includes entity_type envelope for generic validator
                unified_dict = {"entity_type": entity_type, **raw_dict}
                unified_file.write(json.dumps(unified_dict) + "\n")

    @staticmethod
    def _write_sqlite(db_path: Path, dataset: SyntheticDataset) -> None:
        if db_path.exists():
            db_path.unlink()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("CREATE TABLE actors (actor_id TEXT PRIMARY KEY, platform_id TEXT, created_at TEXT, display_name_hash TEXT, payload JSON)")
        cursor.execute("CREATE TABLE spaces (space_id TEXT PRIMARY KEY, kind TEXT, popularity_percentile REAL, audience_context TEXT, payload JSON)")
        cursor.execute("CREATE TABLE content (content_id TEXT PRIMARY KEY, actor_id TEXT, space_id TEXT, kind TEXT, text TEXT, created_at TEXT)")
        cursor.execute("CREATE TABLE media (media_id TEXT PRIMARY KEY, actor_id TEXT, role TEXT, phash TEXT, gate_result TEXT, payload JSON)")
        cursor.execute("CREATE TABLE links (link_id TEXT PRIMARY KEY, actor_id TEXT, domain TEXT, url TEXT, payload JSON)")
        cursor.execute("CREATE TABLE relations (src TEXT, dst TEXT, type TEXT, ts TEXT)")

        for a in dataset.actors:
            cursor.execute("INSERT INTO actors VALUES (?, ?, ?, ?, ?)", (a.actor_id, a.platform_id, a.created_at.isoformat(), a.display_name_hash, json.dumps(a.model_dump(mode="json"))))
        for s in dataset.spaces:
            cursor.execute("INSERT INTO spaces VALUES (?, ?, ?, ?, ?)", (s.space_id, s.kind.value, s.popularity.percentile, s.audience_context.value, json.dumps(s.model_dump(mode="json"))))
        for c in dataset.content:
            cursor.execute("INSERT INTO content VALUES (?, ?, ?, ?, ?, ?)", (c.content_id, c.actor_id, c.space_id, c.kind.value, c.text, c.created_at.isoformat()))
        for m in dataset.media:
            ph = m.perceptual_hashes.get("phash", "")
            gr = m.gate_result.value if m.gate_result else None
            cursor.execute("INSERT INTO media VALUES (?, ?, ?, ?, ?, ?)", (m.media_id, m.actor_id, m.role.value, ph, gr, json.dumps(m.model_dump(mode="json"))))
        for l in dataset.links:
            cursor.execute("INSERT INTO links VALUES (?, ?, ?, ?, ?)", (l.link_id, l.actor_id, l.domain, l.url_normalized, json.dumps(l.model_dump(mode="json"))))
        for r in dataset.relations:
            cursor.execute("INSERT INTO relations VALUES (?, ?, ?, ?)", (r.src, r.dst, r.type.value, r.ts.isoformat()))

        conn.commit()
        conn.close()

    @staticmethod
    def _file_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
