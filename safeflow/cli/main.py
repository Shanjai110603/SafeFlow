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


@app.command(name="generate")
def generate_command(
    profile: str = typer.Option("video_comments", "--profile", "-p", help="Platform profile: video_comments, forum_communities, chat_servers."),
    variant: str = typer.Option("A", "--variant", "-v", help="Dataset variant: 'A' (dev) or 'B' (held-out)."),
    seed: int = typer.Option(42, "--seed", "-s", help="Deterministic RNG seed."),
    actors: int = typer.Option(1000, "--actors", "-n", help="Total actors to generate."),
    base_rate: float = typer.Option(0.05, "--base-rate", "-b", help="Attack base rate (0.05 = 5%)."),
    out: Path = typer.Option(Path("datasets"), "--out", "-o", help="Output directory for generated dataset."),
) -> None:
    """Generate deterministic synthetic datasets across platform profiles."""
    from safeflow.adapters.synthetic.generator import SyntheticGenerator
    from safeflow.adapters.synthetic.models import GeneratorConfig
    from safeflow.adapters.synthetic.exporter import DatasetExporter

    target_dir = out / f"{profile}_{variant}"
    cfg = GeneratorConfig(
        seed=seed,
        variant=variant,  # type: ignore[arg-type]
        platform_profile=profile,  # type: ignore[arg-type]
        actor_count=actors,
        base_rate=base_rate,
    )

    typer.echo(f"Generating synthetic dataset [profile={profile}, variant={variant}, seed={seed}, actors={actors}]...")
    gen = SyntheticGenerator(cfg)
    dataset = gen.generate()

    manifest = DatasetExporter.export(dataset, target_dir)
    typer.echo(f"Exported dataset successfully to {target_dir}:")
    typer.echo(f"  - Manifest: {target_dir / 'manifest.json'}")
    typer.echo(f"  - SQLite DB: {target_dir / f'synthetic_{profile}_{variant}.db'}")
    for ent, count in manifest["entity_counts"].items():
        typer.echo(f"  - {ent.capitalize()}: {count}")


@app.command(name="validate-dataset")
def validate_dataset_command(
    dir: Path = typer.Option(..., "--dir", "-d", help="Directory containing dataset JSONL files."),
) -> None:
    """Validate a synthetic dataset directory against canonical schemas."""
    from safeflow.adapters.generic_jsonl.validator import GenericJSONLValidator

    if not dir.exists():
        typer.echo(f"Error: Directory not found: {dir}", err=True)
        raise typer.Exit(code=1)

    dataset_jsonl = dir / "dataset.jsonl"
    if not dataset_jsonl.exists():
        typer.echo(f"Error: {dataset_jsonl} not found in {dir}.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Validating canonical schema for {dataset_jsonl}...")
    try:
        counts = GenericJSONLValidator.validate_file(dataset_jsonl)
        typer.echo("Schema Validation PASSED (100% compliant with schema_version 1.0.0):")
        for ent, count in counts.items():
            if count > 0:
                typer.echo(f"  - {ent}: {count} valid records")
    except Exception as e:
        typer.echo(f"Validation FAILED: {e}", err=True)
        raise typer.Exit(code=1)


@app.command(name="eval")
def eval_command(
    profile: str = typer.Option("video_comments", "--profile", "-p", help="Platform profile to evaluate."),
    seed: int = typer.Option(42, "--seed", "-s", help="Deterministic RNG seed."),
    actors: int = typer.Option(200, "--actors", "-n", help="Total actors per dataset."),
    out: Path = typer.Option(Path("results"), "--out", "-o", help="Directory to save evaluation reports."),
) -> None:
    """Run full benchmark evaluation, ablations, and cross-platform transfer matrix."""
    from safeflow.eval.runner import EvaluationRunner

    typer.echo(f"Starting SafeFlow Benchmark Evaluation [profile={profile}, seed={seed}, actors={actors}]...")
    res = EvaluationRunner.run_benchmark(
        profile=profile,
        seed=seed,
        actor_count=actors,
        out_dir=out,
    )
    m = res["metrics"]
    typer.echo("\n=======================================================")
    typer.echo(f" SafeFlow Benchmark Results: {profile} (Variant B Test)")
    typer.echo("=======================================================")
    typer.echo(f"  - Precision: {m.precision:.4f}")
    typer.echo(f"  - Recall:    {m.recall:.4f}")
    typer.echo(f"  - F1 Score:  {m.f1:.4f}")
    typer.echo(f"  - PR-AUC:    {m.pr_auc:.4f}")
    typer.echo(f"  - ROC-AUC:   {m.roc_auc:.4f}")
    typer.echo(f"  - P@10:      {m.precision_at_10:.4f}")
    typer.echo(f"  - P@50:      {m.precision_at_50:.4f}")
    typer.echo("=======================================================")
    typer.echo(f"Saved artifacts to {res['run_dir']}:")
    typer.echo(f"  - metrics.json")
    typer.echo(f"  - transfer_matrix.csv")
    typer.echo(f"  - summary.md\n")


if __name__ == "__main__":
    app()

