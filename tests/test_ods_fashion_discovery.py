from opportunity_engine.ods import (
    FashionDiscoveryPlugin,
    ODSRequest,
    ODSSession,
    PluginRegistry,
    Stage,
    Status,
    WorkflowEngine,
)


def test_fashion_discovery_returns_curated_opportunities() -> None:
    plugin = FashionDiscoveryPlugin()
    session = ODSSession(
        request=ODSRequest(subject="Fashion", country="Norway")
    )

    result = plugin.run(session)

    assert result.stage is Stage.DISCOVERY
    assert result.status is Status.COMPLETED
    assert len(result.payload) == 10
    assert len({item.opportunity_id for item in result.payload}) == 10
    assert all(item.source_plugin.startswith("fashion_discovery:") for item in result.payload)
    assert all("Norway" in item.description for item in result.payload)
    assert len(result.evidence) == 5


def test_fashion_discovery_accepts_arabic_alias() -> None:
    plugin = FashionDiscoveryPlugin()
    session = ODSSession(request=ODSRequest(subject="أزياء", country="Norway"))

    result = plugin.run(session)

    assert result.status is Status.COMPLETED
    assert len(result.payload) == 10


def test_fashion_discovery_rejects_unsupported_sector() -> None:
    plugin = FashionDiscoveryPlugin()
    session = ODSSession(request=ODSRequest(subject="Restaurants"))

    result = plugin.run(session)

    assert result.status is Status.FAILED
    assert result.payload is None
    assert result.errors


def test_discovery_plugin_runs_inside_ods_workflow() -> None:
    registry = PluginRegistry([FashionDiscoveryPlugin()])
    engine = WorkflowEngine(registry, workflow=(Stage.DISCOVERY,))

    session = engine.run(ODSRequest(subject="ملابس", country="Norway"))

    assert session.status is Status.COMPLETED
    assert session.current_stage is None
    assert len(session.results[Stage.DISCOVERY].payload) == 10
    assert session.audit_log == [
        "session_started",
        "stage_started:discovery",
        "stage_completed:discovery",
        "session_completed",
    ]
