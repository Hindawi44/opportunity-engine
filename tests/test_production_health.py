import json

from opportunity_engine.ods.production_health import ProductionHealthChecker


def test_health_check_passes_with_optional_connectors_disabled(tmp_path) -> None:
    report = ProductionHealthChecker().run(data_directory=tmp_path, environment={})

    assert report.ready is True
    assert report.status == "healthy"
    assert any(item.name == "data_directory" and item.status == "pass" for item in report.checks)
    assert all(item.status != "fail" for item in report.checks)


def test_health_check_rejects_partial_connector_configuration(tmp_path) -> None:
    report = ProductionHealthChecker().run(
        data_directory=tmp_path,
        environment={"FINN_API_KEY": "secret"},
    )

    assert report.ready is False
    item = next(item for item in report.checks if item.name == "connector:FINN.no")
    assert item.status == "fail"
    assert "FINN_ORG_ID" in item.message


def test_health_report_is_written_atomically(tmp_path) -> None:
    output = tmp_path / "health.json"
    report = ProductionHealthChecker().write_report(
        output,
        data_directory=tmp_path / "data",
        environment={},
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ready"] is report.ready
    assert payload["status"] == "healthy"
    assert payload["checks"]
    assert not (tmp_path / "health.json.tmp").exists()
