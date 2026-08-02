from pathlib import Path


REPORT_PATH = Path("docs/WORKFLOW_INVENTORY_REPORT_v1.2.md")
WORKFLOW_DIR = Path(".github/workflows")


def test_workflow_inventory_report_represents_every_workflow_file() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    workflow_paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))

    assert workflow_paths, "No GitHub Actions workflows were found"
    assert len(workflow_paths) == 37

    missing = [path.as_posix() for path in workflow_paths if f"`{path.as_posix()}`" not in report]
    assert missing == []


def test_workflow_inventory_report_preserves_safe_scope() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "Workflow files represented:** 37" in report
    assert "Germany Clothing Inventory open-web pilot" in report
    assert "Riegermann active-auction workflow" in report
    assert "VENTA active-catalog watch" in report
    assert "Deutsche Pfandverwertung watch" in report
    assert "MULTI_MARKET_OPERATOR_CHECKPOINT" in report
    assert "manual read-only NO/SE/DE" in report
    assert "PRIMARY_DISCOVERY_CANDIDATE" in report
    assert "END_TO_END_REVIEW_CANDIDATE" in report
    assert "contacts sellers, bids, buys, pays" in report
    assert "market identity `DE`" in report
    assert "currency `EUR`" in report
    assert "no use of `price_nok` or `bid_price_nok`" in report
    assert "zero-result run remains a valid" in report
