import json

from opportunity_engine.production_readiness import ProductionReadinessAuditor


def test_readiness_passes_with_safe_limits_and_secret(tmp_path):
    script = tmp_path / "run_daily_pipeline.py"
    script.write_text("print('ok')", encoding="utf-8")
    report = ProductionReadinessAuditor().audit(
        environment={
            "BRAVE_API_KEY": "configured",
            "BRAVE_MAX_REQUESTS_PER_RUN": "4",
            "BRAVE_CACHE_TTL_HOURS": "24",
        },
        daily_script=script,
        investment_files_dir=tmp_path / "investment_files",
        usage_log=tmp_path / "logs" / "brave_usage.jsonl",
    )
    assert report.ready is True
    assert all(check.passed for check in report.checks if check.required)


def test_readiness_never_exposes_secret(tmp_path):
    secret = "do-not-print-this"
    script = tmp_path / "run_daily_pipeline.py"
    script.write_text("pass", encoding="utf-8")
    report = ProductionReadinessAuditor().audit(
        environment={"BRAVE_API_KEY": secret},
        daily_script=script,
        investment_files_dir=tmp_path / "files",
        usage_log=tmp_path / "usage.jsonl",
    )
    assert secret not in json.dumps(report.to_dict())


def test_missing_secret_blocks_live_readiness(tmp_path):
    script = tmp_path / "run_daily_pipeline.py"
    script.write_text("pass", encoding="utf-8")
    report = ProductionReadinessAuditor().audit(
        environment={},
        daily_script=script,
        investment_files_dir=tmp_path / "files",
        usage_log=tmp_path / "usage.jsonl",
    )
    assert report.ready is False


def test_dry_run_comparison_detects_repeat_protection(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps({"external_searches_executed": 4}), encoding="utf-8")
    second.write_text(json.dumps({"external_searches_executed": 0, "external_cache_hits": 4}), encoding="utf-8")
    result = ProductionReadinessAuditor.inspect_dry_run(first, second)
    assert result["repeat_protection_observed"] is True
