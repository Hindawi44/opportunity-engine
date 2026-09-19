from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_cross_source_checkpoint_adapter.py"
WORKFLOW = ROOT / ".github" / "workflows" / "multi-market-daily-operator-checkpoint.yaml"
LEGACY = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"


def _module():
    spec = spec_from_file_location("cross_source_checkpoint_adapter", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adapter_preserves_verified_active_candidate_and_safety() -> None:
    module = _module()
    record = module._normalize_candidate({
        "title": "Verified clothing stock lot", "url": "https://example.test/lot/1",
        "listing_status": "ACTIVE", "source_channel": "KONKURS_APP_AUKSJONEN_EXACT_ORGNR",
        "top5_eligible": True, "analysis_eligible": True,
    })
    assert record["discovery_score"] == 100
    assert record["currency"] == "NOK"
    assert record["opportunity_state"] == "ACTIVE_OPPORTUNITY"
    assert record["automatic_contact"] is False
    assert record["automatic_bid"] is False
    assert record["automatic_purchase_decision"] is False
    assert record["automatic_payment"] is False


def test_adapter_writes_standard_checkpoint_artifact_names() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for marker in ('"search-run-report.json"', '"all-discovered-candidates.json"',
                   '"discovery-top5.json"', '"discovered_at": discovered_at',
                   '"market_code": "NO"', '"currency": "NOK"',
                   '"paid_search_used": False', '"openai_api_used": False',
                   '"automatic_purchase": False'):
        assert marker in text


def test_adapter_emits_parseable_utc_discovered_at_for_continuity(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    output_dir = tmp_path / "no-cross-source"
    output_dir.mkdir()
    (output_dir / "multi-source-live-report.json").write_text(
        json.dumps({"scan_complete": True, "errors": 0}), encoding="utf-8")
    (output_dir / "live-clothing-top5.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(module.sys, "argv", ["run_cross_source_checkpoint_adapter.py", "--output-dir", str(output_dir)])
    assert module.main() == 0
    report = json.loads((output_dir / "search-run-report.json").read_text(encoding="utf-8"))
    discovered_at = datetime.fromisoformat(report["discovered_at"])
    assert discovered_at.tzinfo is not None
    assert discovered_at.utcoffset() is not None
    assert report["status"] == "PASS"


def test_sixteen_country_source_contract_is_archived_not_live() -> None:
    old = LEGACY.read_text(encoding="utf-8")
    live = WORKFLOW.read_text(encoding="utf-8")
    assert 'len(report.get("sources") or []) != 16' in old
    assert '"source_name": "Norway cross-source verification"' in old
    assert "Run Norway bounded cross-source verification" in old
    assert 'cron: "47 0-6 * * *"' in old
    assert live.startswith("name: Norway Opportunity Hunter\n")
    assert "Run Sweden Blinto bounded pilot" not in live
    assert "Run Sen & Sen bounded clothing liquidation scan" not in live
