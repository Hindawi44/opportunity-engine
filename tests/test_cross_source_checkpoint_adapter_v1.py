from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_cross_source_checkpoint_adapter.py"
WORKFLOW = ROOT / ".github" / "workflows" / "multi-market-daily-operator-checkpoint.yaml"


def _module():
    spec = spec_from_file_location("cross_source_checkpoint_adapter", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adapter_preserves_verified_active_candidate_and_safety() -> None:
    module = _module()
    record = module._normalize_candidate(
        {
            "title": "Verified clothing stock lot",
            "url": "https://example.test/lot/1",
            "listing_status": "ACTIVE",
            "source_channel": "KONKURS_APP_AUKSJONEN_EXACT_ORGNR",
            "top5_eligible": True,
            "analysis_eligible": True,
        }
    )

    assert record["discovery_score"] == 100
    assert record["currency"] == "NOK"
    assert record["opportunity_state"] == "ACTIVE_OPPORTUNITY"
    assert record["automatic_contact"] is False
    assert record["automatic_bid"] is False
    assert record["automatic_purchase_decision"] is False
    assert record["automatic_payment"] is False


def test_adapter_writes_standard_checkpoint_artifact_names() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '"search-run-report.json"' in text
    assert '"all-discovered-candidates.json"' in text
    assert '"discovery-top5.json"' in text
    assert '"discovered_at": discovered_at' in text
    assert '"market_code": "NO"' in text
    assert '"currency": "NOK"' in text
    assert '"paid_search_used": False' in text
    assert '"openai_api_used": False' in text
    assert '"automatic_purchase": False' in text


def test_adapter_emits_parseable_utc_discovered_at_for_continuity(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    output_dir = tmp_path / "no-cross-source"
    output_dir.mkdir()
    (output_dir / "multi-source-live-report.json").write_text(
        json.dumps({"scan_complete": True, "errors": 0}),
        encoding="utf-8",
    )
    (output_dir / "live-clothing-top5.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["run_cross_source_checkpoint_adapter.py", "--output-dir", str(output_dir)],
    )

    assert module.main() == 0

    report = json.loads(
        (output_dir / "search-run-report.json").read_text(encoding="utf-8")
    )
    discovered_at = datetime.fromisoformat(report["discovered_at"])
    assert discovered_at.tzinfo is not None
    assert discovered_at.utcoffset() is not None
    assert report["status"] == "PASS"


def test_daily_checkpoint_runs_cross_source_as_seventh_bounded_source() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Run Norway bounded cross-source verification" in text
    assert "run_cross_source_checkpoint_adapter.py" in text
    assert '"source_name": "Norway cross-source verification"' in text
    assert '"artifact_dir": "artifacts/multi-market-inputs/no-cross-source"' in text
    assert 'len(report.get("sources") or []) != 7' in text
    assert 'sum((report.get("source_execution_counts") or {}).values()) != 7' in text
    assert 'cron: "17 5 * * *"' in text
