from dataclasses import dataclass

import pytest

from opportunity_engine.ods import (
    ODSRequest,
    PluginRegistry,
    Stage,
    StageResult,
    Status,
    WorkflowEngine,
)


@dataclass
class StubPlugin:
    name: str
    stage: Stage
    payload: object = None
    status: Status = Status.COMPLETED

    def run(self, session):
        return StageResult(stage=self.stage, status=self.status, payload=self.payload)


def test_request_rejects_empty_subject():
    with pytest.raises(ValueError, match="subject"):
        ODSRequest(subject="   ")


def test_registry_rejects_duplicate_stage():
    registry = PluginRegistry([StubPlugin("first", Stage.DISCOVERY)])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(StubPlugin("second", Stage.DISCOVERY))


def test_workflow_runs_stages_in_order_and_records_audit_log():
    registry = PluginRegistry(
        [
            StubPlugin("discovery", Stage.DISCOVERY, ["opportunity"]),
            StubPlugin("ranking", Stage.RANKING, ["ranked"]),
        ]
    )
    engine = WorkflowEngine(
        registry,
        workflow=(Stage.DISCOVERY, Stage.RANKING),
    )

    session = engine.run(ODSRequest(subject="Fashion", country="Norway"))

    assert session.status is Status.COMPLETED
    assert list(session.results) == [Stage.DISCOVERY, Stage.RANKING]
    assert session.audit_log == [
        "session_started",
        "stage_started:discovery",
        "stage_completed:discovery",
        "stage_started:ranking",
        "stage_completed:ranking",
        "session_completed",
    ]


def test_workflow_stops_when_plugin_is_missing():
    engine = WorkflowEngine(
        PluginRegistry([StubPlugin("discovery", Stage.DISCOVERY)]),
        workflow=(Stage.DISCOVERY, Stage.RANKING),
    )

    session = engine.run(ODSRequest(subject="Fashion"))

    assert session.status is Status.FAILED
    assert Stage.DISCOVERY in session.results
    assert Stage.RANKING not in session.results
    assert session.audit_log[-1].startswith("stage_failed:ranking")


def test_workflow_stops_on_non_completed_result():
    engine = WorkflowEngine(
        PluginRegistry(
            [StubPlugin("discovery", Stage.DISCOVERY, status=Status.FAILED)]
        ),
        workflow=(Stage.DISCOVERY,),
    )

    session = engine.run(ODSRequest(subject="Fashion"))

    assert session.status is Status.FAILED
    assert session.results[Stage.DISCOVERY].status is Status.FAILED
