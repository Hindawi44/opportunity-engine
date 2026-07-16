"""Plugin contracts and registry for ODS Core."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .models import ODSSession, Stage, StageResult


class ODSPlugin(Protocol):
    """Minimal contract every ODS stage plugin must implement."""

    name: str
    stage: Stage

    def run(self, session: ODSSession) -> StageResult:
        """Run the plugin for the current session."""


class PluginRegistry:
    """Stores one active plugin per workflow stage."""

    def __init__(self, plugins: Iterable[ODSPlugin] = ()) -> None:
        self._plugins: dict[Stage, ODSPlugin] = {}
        for plugin in plugins:
            self.register(plugin)

    def register(self, plugin: ODSPlugin) -> None:
        if plugin.stage in self._plugins:
            raise ValueError(f"plugin already registered for stage: {plugin.stage.value}")
        self._plugins[plugin.stage] = plugin

    def get(self, stage: Stage) -> ODSPlugin:
        try:
            return self._plugins[stage]
        except KeyError as exc:
            raise LookupError(f"no plugin registered for stage: {stage.value}") from exc

    def has(self, stage: Stage) -> bool:
        return stage in self._plugins
