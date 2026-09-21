"""SignalPlugin protocol and dynamic plugin registry.

Core maintains the protocol and registry but never imports plugin implementations directly.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel
from safeflow.core.schema import Signal


@runtime_checkable
class SignalPlugin(Protocol):
    """Protocol that all SafeFlow signal plugins must implement."""

    @property
    def name(self) -> str:
        """Unique plugin identifier (e.g. 'image_gate', 'media_reuse')."""
        ...

    @property
    def family(self) -> str:
        """Signal family (e.g. 'IMAGE_LINK', 'BEHAVIOR', 'DESTINATION')."""
        ...

    @property
    def version(self) -> str:
        """Plugin semantic version."""
        ...

    @property
    def requires(self) -> list[str]:
        """Required entity kinds (e.g. ['media'], ['actor', 'content'])."""
        ...

    def run(self, batch: list[Any], context: dict[str, Any] | None = None) -> list[Signal]:
        """Execute signal detection over a batch of canonical entities."""
        ...

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return the Pydantic configuration schema for this plugin, if any."""
        ...


class PluginRegistry:
    """Central registry managing discovery and lifecycle of SignalPlugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, SignalPlugin] = {}

    def register(self, plugin: SignalPlugin) -> None:
        """Register a SignalPlugin instance."""
        if not isinstance(plugin, SignalPlugin):
            raise TypeError(f"Object {plugin} does not implement the SignalPlugin protocol.")
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> bool:
        return self._plugins.pop(name, None) is not None

    def get(self, name: str) -> SignalPlugin | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[SignalPlugin]:
        return list(self._plugins.values())

    def get_enabled(self, enabled_names: list[str]) -> list[SignalPlugin]:
        """Return registered plugins that are enabled in the active policy pack."""
        return [self._plugins[name] for name in enabled_names if name in self._plugins]

    def clear(self) -> None:
        self._plugins.clear()


# Global default registry instance
global_plugin_registry = PluginRegistry()
