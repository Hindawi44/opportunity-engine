"""Sequential, auditable workflow engine for ODS Core v1 alpha."""

from __future__ import annotations

from collections.abc import Iterable

from .models import ODSRequest, ODSSession, Stage, Status
from .plugins import PluginRegistry


DEFAULT_WORKFLOW: tuple[Stage, ...] = (
    Stage.DISCOVERY,
    Stage.RANKING,
    Stage.BDNA,
    Stage.VALIDATION,
    Stage.EXECUTION,
    Stage.LEARNING,
)


class WorkflowEngine:
    """Runs registered plugins in a fixed stage order.

    ODS Core owns orchestration only. Business reasoning remains inside plugins.
    A missing plugin, failed result, or raised exception stops the session.
    """

    def __init__(
        self,
        registry: PluginRegistry,
        workflow: Iterable[Stage] = DEFAULT_WORKFLOW,
    ) -> None:
        self.registry = registry
        self.workflow = tuple(workflow)
        if not self.workflow:
            raise ValueError("workflow must contain at least one stage")

    def run(self, request: ODSRequest) -> ODSSession:
        session = ODSSession(request=request, status=Status.RUNNING)
        session.record("session_started")

        for stage in self.workflow:
            session.current_stage = stage
            session.record(f"stage_started:{stage.value}")

            try:
                plugin = self.registry.get(stage)
                result = plugin.run(session)
            except Exception as exc:  # Core converts plugin errors into session state.
                session.status = Status.FAILED
                session.record(f"stage_failed:{stage.value}:{exc}")
                return session

            if result.stage is not stage:
                session.status = Status.FAILED
                session.record(
                    f"stage_failed:{stage.value}:plugin returned {result.stage.value}"
                )
                return session

            session.results[stage] = result
            if result.status is not Status.COMPLETED:
                session.status = Status.FAILED
                session.record(f"stage_failed:{stage.value}:non-completed result")
                return session

            session.record(f"stage_completed:{stage.value}")

        session.current_stage = None
        session.status = Status.COMPLETED
        session.record("session_completed")
        return session
