from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/verify_cross_source_exclusion_accounting.py"
)
SPEC = spec_from_file_location("verified_exclusion_accounting", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def item(source: str, record_id: str, url: str) -> dict:
    return {
        "source": source,
        "lead_id": record_id,
        "title": record_id,
        "url": url,
    }


def audit_counts(auksjonen: int = 0, konkurs: int = 0, politiet: int = 0) -> dict:
    return {
        "schema_version": 3,
        "source_record_counts": {
            "Auksjonen.no": auksjonen,
            "Konkurs.app": konkurs,
            "Politiet.no": politiet,
        },
    }


def funnel_counts(auksjonen: int = 0, konkurs: int = 0, politiet: int = 0) -> dict:
    return {
        "Auksjonen.no": auksjonen,
        "Konkurs.app": konkurs,
        "Politiet.no": politiet,
    }


def test_reconciled_source_has_no_invented_exclusions() -> None:
    records = [
        item("Konkurs.app", "k-1", "https://konkurs.app/konkursbo/1"),
        item("Konkurs.app", "k-2", "https://konkurs.app/konkursbo/2"),
    ]
    accounting = MODULE.build_verified_accounting(
        audit_counts(konkurs=2),
        funnel_counts(konkurs=2),
        [("bankruptcy_leads", records)],
    )

    row = accounting["by_source"]["Konkurs.app"]
    assert accounting["valid"] is True
    assert row["equation_holds"] is True
    assert row["verified_excluded_count"] == 0
    assert row["excluded_records_by_reason"] == {}
    assert row["excluded_record_ids"] == []
    assert row["status"] == "RECONCILED"


def test_duplicate_is_counted_only_when_observed_in_input_channels() -> None:
    record = item("Konkurs.app", "k-1", "https://konkurs.app/konkursbo/1")
    accounting = MODULE.build_verified_accounting(
        audit_counts(konkurs=1),
        funnel_counts(konkurs=2),
        [("discovery", [record]), ("bankruptcy_leads", [record])],
    )

    row = accounting["by_source"]["Konkurs.app"]
    assert accounting["valid"] is True
    assert row["verified_excluded_count"] == 1
    assert row["excluded_records_by_reason"] == {
        MODULE.DUPLICATE_REASON: 1,
    }
    assert row["excluded_record_ids"] == ["k-1"]
    assert row["accounted_total"] == 2


def test_missing_konkurs_records_fail_without_verified_exclusions() -> None:
    accounting = MODULE.build_verified_accounting(
        audit_counts(konkurs=0),
        funnel_counts(konkurs=3),
        [],
    )

    row = accounting["by_source"]["Konkurs.app"]
    assert accounting["valid"] is False
    assert row["verified_excluded_count"] == 0
    assert row["excluded_records_by_reason"] == {}
    assert row["excluded_record_ids"] == []
    assert row["difference"] == 3
    assert row["equation_holds"] is False
    assert row["status"] == "UNEXPLAINED_LOSS"


def test_partial_unexplained_loss_also_fails_exact_equation() -> None:
    records = [item("Konkurs.app", "k-1", "https://konkurs.app/konkursbo/1")]
    accounting = MODULE.build_verified_accounting(
        audit_counts(konkurs=1),
        funnel_counts(konkurs=3),
        [("bankruptcy_leads", records)],
    )

    row = accounting["by_source"]["Konkurs.app"]
    assert accounting["valid"] is False
    assert row["audit_record_count"] == 1
    assert row["verified_excluded_count"] == 0
    assert row["accounted_total"] == 1
    assert row["difference"] == 2


def test_report_persists_required_verified_exclusion_fields() -> None:
    accounting = MODULE.build_verified_accounting(
        audit_counts(konkurs=0),
        funnel_counts(konkurs=1),
        [],
    )
    payload = MODULE.apply_verified_accounting(audit_counts(), accounting)

    assert payload["schema_version"] == 4
    assert payload["excluded_record_count"] == 0
    assert payload["excluded_records_by_reason"] == {}
    assert payload["excluded_record_ids"] == []
    assert payload["verified_exclusion_accounting_valid"] is False
    assert "Konkurs.app" in payload["verified_exclusion_accounting"]
