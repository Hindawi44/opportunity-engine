import json
from datetime import date

from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.finn import FinnApiClient
from opportunity_engine.ods.live_data import SourceDocument


class _AuksjonenStub:
    def search(self, *, keyword=None):
        return (
            SourceDocument(
                document_id="auksjonen-1",
                source_name="Auksjonen.no",
                source_type="public_auction_listing",
                title="Butikkinnredning",
                text="Butikkinnredning",
                url="https://www.auksjonen.no/auksjon/1",
                country="Norway",
                metadata={"current_price_nok": 1000, "mva_status": "included"},
            ),
        )


class _FailingAuksjonenStub:
    def search(self, *, keyword=None):
        raise RuntimeError("temporary source failure")


FINN_FEED = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>urn:finn:987654</id>
    <title>Kontormobler</title>
    <summary>Brukte kontormobler</summary>
    <updated>2026-07-20T08:00:00Z</updated>
    <link rel="self" href="https://www.finn.no/bap/forsale/ad.html?finnkode=987654" />
  </entry>
</feed>'''


def _finn_client():
    return FinnApiClient(
        api_key="secret",
        org_id="123",
        transport=lambda url, timeout, headers: FINN_FEED,
    )


def _config(tmp_path):
    return DailyPipelineConfig(
        output_path=str(tmp_path / "today.json"),
        history_path=str(tmp_path / "history.json"),
    )


def test_pipeline_combines_auksjonen_and_authorized_finn(tmp_path) -> None:
    config = _config(tmp_path)
    result = AutomatedDailyPipeline(
        client=_AuksjonenStub(),
        finn_client=_finn_client(),
    ).run(config, report_date=date(2026, 7, 20))

    payload = json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))
    assert result.fetched_count == 2
    assert result.deduplicated_count == 2
    assert result.source_counts == {"Auksjonen.no": 1, "FINN.no": 1}
    assert result.source_errors == {}
    assert payload["schema_version"] == 11
    assert payload["sources"]["FINN.no"] == 1
    assert payload["total_count"] == 2
    assert len(payload["intelligence_by_id"]) == 2
    assert len(payload["discovery_by_id"]) == 2


def test_one_source_failure_does_not_stop_other_source(tmp_path) -> None:
    result = AutomatedDailyPipeline(
        client=_FailingAuksjonenStub(),
        finn_client=_finn_client(),
    ).run(_config(tmp_path))

    assert result.fetched_count == 1
    assert result.source_counts == {"Auksjonen.no": 0, "FINN.no": 1}
    assert "Auksjonen.no" in result.source_errors


def test_finn_is_optional_when_not_configured(tmp_path) -> None:
    result = AutomatedDailyPipeline(client=_AuksjonenStub()).run(_config(tmp_path))

    assert result.source_counts == {"Auksjonen.no": 1}
    assert "FINN.no" not in result.source_counts
