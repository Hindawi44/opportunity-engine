from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/verify_cross_source_record_accounting.py"
)
SPEC = spec_from_file_location("cross_source_record_accounting", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _item(source: str, record_id: str, url: str) -> dict:
    return {
        "source": source,
        "lead_id": record_id,
        "title": record_id,
        "url": url,
    }


def test_selected_bankruptcy_lead_is_not_double_counted_as_excluded() -> None:
    audit_payload = {
        "source_record_counts": {
            "Auksjonen.no": 2,
            "Konkurs.app": 1,
            "Politiet.no": 0,
        }
    }
    funnel_counts = {
        "Auksjonen.no": 3,
        "Konkurs.app": 3,
        "Politiet.no": 0,
    }
    groups = [
        (
            "daily",
            [
                _item("Auksjonen.no", "a-1", "https://auksjonen.no/auksjon/1"),
                _item("Auksjonen.no", "a-2", "https://auksjonen.no/auksjon/2"),
            ],
        ),
        (
            "bankruptcy_leads",
            [_item("Konkurs.app", "k-1", "https://konkurs.app/konkursbo/1")],
        ),
    ]
    pipeline_exclusions = {
        "Auksjonen.no": [
            {"record_id": "a-3", "reason": "daily_report_limit", "channel": "daily_report"}
        ],
        "Konkurs.app": [
            {"record_id": "k-1", "reason": "unsupported", "channel": "extraction"},
            {"record_id": "k-2", "reason": "unsupported", "channel": "extraction"},
            {"record_id": "k-3", "reason": "unsupported", "channel": "extraction"},
        ],
        "Politiet.no": [],
    }

    accounting = MODULE.build_record_accounting(
        audit_payload,
        funnel_counts,
        groups,
        pipeline_exclusions,
    )

    assert accounting["valid"] is True
    auksjonen = accounting["by_source"]["Auksjonen.no"]
    konkurs = accounting["by_source"]["Konkurs.app"]
    assert auksjonen["audit_record_count"] == 2
    assert auksjonen["pipeline_excluded_count"] == 1
    assert auksjonen["accounted_total"] == 3
    assert konkurs["audit_record_count"] == 1
    assert konkurs["pipeline_excluded_count"] == 2
    assert konkurs["excluded_record_ids"] == ["k-2", "k-3"]
    assert konkurs["accounted_total"] == 3


def test_unexplained_fetched_record_still_fails() -> None:
    audit_payload = {
        "source_record_counts": {
            "Auksjonen.no": 1,
            "Konkurs.app": 0,
            "Politiet.no": 0,
        }
    }
    accounting = MODULE.build_record_accounting(
        audit_payload,
        {"Auksjonen.no": 2, "Konkurs.app": 0, "Politiet.no": 0},
        [
            (
                "daily",
                [_item("Auksjonen.no", "a-1", "https://auksjonen.no/auksjon/1")],
            )
        ],
        {source: [] for source in MODULE.OFFICIAL_SOURCES},
    )

    assert accounting["valid"] is False
    assert accounting["by_source"]["Auksjonen.no"]["difference"] == 1
    assert accounting["by_source"]["Auksjonen.no"]["status"] == "UNEXPLAINED_LOSS"
