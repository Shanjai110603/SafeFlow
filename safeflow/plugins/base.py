"""Base abstractions for SignalPlugins."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel
from safeflow.core.registry import SignalPlugin
from safeflow.core.schema import Signal


class BaseSignalPlugin:
    """Convenience base class for SignalPlugins."""

    name: str = "base_plugin"
    family: str = "GENERIC"
    version: str = "1.0.0"
    requires: list[str] = []

    def get_config_schema(self) -> type[BaseModel] | None:
        return None

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        raise NotImplementedError
