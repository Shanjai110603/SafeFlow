"""Synthetic data adapter package."""

from __future__ import annotations

from safeflow.adapters.synthetic.generator import SyntheticDataset, SyntheticGenerator
from safeflow.adapters.synthetic.models import AttackCategory, GeneratorConfig, GroundTruthMetadata, LegitCategory
from safeflow.adapters.synthetic.exporter import DatasetExporter
from safeflow.adapters.synthetic.profiles import get_platform_profile

__all__ = [
    "AttackCategory",
    "DatasetExporter",
    "GeneratorConfig",
    "GroundTruthMetadata",
    "LegitCategory",
    "SyntheticDataset",
    "SyntheticGenerator",
    "get_platform_profile",
]
