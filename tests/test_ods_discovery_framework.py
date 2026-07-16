from opportunity_engine.ods import (
    CuratedDiscoveryPlugin,
    ODSRequest,
    ODSSession,
    OpportunitySeed,
    Scanner,
    Status,
)


class DemoDiscoveryPlugin(CuratedDiscoveryPlugin):
    name = "demo_discovery"
    sector_key = "demo"
    aliases = frozenset({"demo", "تجربة"})
    scanners = (
        Scanner(
            name="problem",
            seeds=(
                OpportunitySeed(
                    title="Shared testing service",
                    description="A shared service for teams in {market}.",
                    category="service",
                    evidence=("problem:duplicated testing work",),
                    confidence=0.71,
                ),
            ),
        ),
    )


def test_generic_framework_supports_multilingual_aliases() -> None:
    plugin = DemoDiscoveryPlugin()
    session = ODSSession(request=ODSRequest(subject="تجربة", country="Norway"))

    result = plugin.run(session)

    assert result.status is Status.COMPLETED
    assert len(result.payload) == 1
    assert result.payload[0].opportunity_id == "demo-problem-shared-testing-service"
    assert result.payload[0].source_plugin == "demo_discovery:problem"
    assert "Norway" in result.payload[0].description


def test_generic_framework_rejects_unsupported_subject() -> None:
    plugin = DemoDiscoveryPlugin()
    session = ODSSession(request=ODSRequest(subject="fashion"))

    result = plugin.run(session)

    assert result.status is Status.FAILED
    assert result.payload is None
    assert "does not support subject" in result.errors[0]


def test_scanner_adds_market_when_template_omits_it() -> None:
    scanner = Scanner(
        name="trend",
        seeds=(
            OpportunitySeed(
                title="Reusable workflow",
                description="A reusable workflow for small teams.",
                category="workflow",
                evidence=("pattern:reuse",),
                confidence=0.6,
            ),
        ),
    )

    candidates = scanner.scan(
        sector_key="demo",
        plugin_name="demo_discovery",
        country="Norway",
    )

    assert len(candidates) == 1
    assert candidates[0].description.endswith("Market: Norway.")
