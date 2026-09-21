"""SafeFlow Command Line Interface.

Commands:
- safeflow gate: Evaluate an image against a policy pack with role-based output.
- safeflow schema export: Export canonical JSON Schemas.
- safeflow db init: Initialize SQLite database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
import typer
from safeflow.core.config import PolicyPackLoader
from safeflow.core.database import DatabaseManager
from safeflow.core.roles import RoleRedactor, UserRole
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
from safeflow.plugins.image_gate.pipeline import ImageGatePipeline

app = typer.Typer(
    name="safeflow",
    help="SafeFlow: Trust & Safety Signal and Decision Engine CLI.",
    add_completion=False,
)


@app.command(name="gate")
def gate_command(
    file: Path = typer.Option(..., "--file", "-f", help="Path to avatar image file to assess."),
    pack: str = typer.Option("general_video_platform", "--pack", "-p", help="Policy pack name."),
    role: str = typer.Option("analyst", "--role", "-r", help="Access role: 'analyst' or 'creator'."),
    db_url: str = typer.Option("sqlite:///:memory:", "--db", help="Database connection URL."),
) -> None:
    """Evaluate an uploaded profile avatar through the Profile Image Safety Gate."""
    if not file.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(code=1)

    try:
        user_role = UserRole(role.lower())
    except ValueError:
        typer.echo(f"Error: Invalid role '{role}'. Must be 'analyst' or 'creator'.", err=True)
        raise typer.Exit(code=1)

    try:
        policy = PolicyPackLoader.load_by_name(pack)
    except Exception as e:
        typer.echo(f"Error loading policy pack '{pack}': {e}", err=True)
        raise typer.Exit(code=1)

    pipeline = ImageGatePipeline()
    image_bytes = file.read_bytes()

    try:
        raw_result = pipeline.process(
            image_bytes=image_bytes,
            policy_pack=policy,
            actor_id="cli_actor",
            media_id=file.stem
        )
    except Exception as e:
        typer.echo(f"Pipeline error: {e}", err=True)
        raise typer.Exit(code=1)

    if user_role == UserRole.CREATOR:
        creator_resp = RoleRedactor.to_creator_response(
            decision=raw_result.decision,
            media_id=file.stem,
            appeal_token=f"appeal_{file.stem}" if raw_result.decision in ("BLOCK", "REVIEW") else None
        )
        typer.echo(json.dumps(creator_resp.model_dump(), indent=2))
    else:
        # Analyst / Admin view
        analyst_view = raw_result.model_dump()
        typer.echo(json.dumps(analyst_view, indent=2))


@app.command(name="schema")
def schema_command(
    action: str = typer.Argument("export", help="Action to perform: 'export'"),
    out_dir: Path = typer.Option(Path("schemas"), "--out", "-o", help="Output directory for JSON schemas."),
) -> None:
    """Export canonical SafeFlow models as JSON Schema files."""
    if action != "export":
        typer.echo(f"Unknown action '{action}'. Use 'safeflow schema export'.", err=True)
        raise typer.Exit(code=1)

    out_dir.mkdir(parents=True, exist_ok=True)
    models = {
        "Actor": Actor,
        "Space": Space,
        "Content": Content,
        "Media": Media,
        "Link": Link,
        "Relation": Relation,
        "Signal": Signal,
        "Decision": Decision,
    }

    exported = []
    for name, model in models.items():
        schema_path = out_dir / f"{name.lower()}.schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(model.model_json_schema(), f, indent=2)
        exported.append(str(schema_path))

    typer.echo(f"Exported {len(exported)} canonical schemas to {out_dir}:")
    for p in exported:
        typer.echo(f"  - {p}")


@app.command(name="db")
def db_command(
    action: str = typer.Argument("init", help="Action: 'init'"),
    db_url: str = typer.Option("sqlite:///safeflow.db", "--db", help="Database connection URL."),
) -> None:
    """Manage SafeFlow database."""
    if action == "init":
        db = DatabaseManager(db_url)
        typer.echo(f"Initialized database schema at {db_url}.")
    else:
        typer.echo(f"Unknown db action '{action}'.", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
