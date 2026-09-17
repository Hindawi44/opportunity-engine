from copy import deepcopy

from opportunity_engine.source_status_reconciliation import reconcile_auksjonen_snapshot


URL = "https://ny.auksjonen.no/auksjon/torget/Sko_Parti_p%C3%A5_3600_par/572303"
CAPTURED = "2026-09-17T00:58:48+00:00"


def queue():
    record = {"identity": "shoes", "title": "3600 shoes", "source_url": URL,
              "stock_confidence": "UNVERIFIED"}
    return {"counts": {"direct_waiting_for_review": 1, "daily_batch": 1, "remaining": 0},
            "capture_timestamp": "2026-09-17T01:06:37+00:00",
            "review_queue": [record], "daily_batch": [record], "held_separately": []}


def snapshot(status="INPROGRESS", ends="2026-09-22T11:58:00+00:00"):
    return {"schema_version": "auksjonen-live-clothing-1.2", "captured_at": CAPTURED,
            "listings": [{"source": "Auksjonen Public API", "url": URL,
                          "status": status, "listing_status": "ACTIVE", "ends_at": ends}]}


def test_real_shoe_snapshot_open_is_dated_but_not_stock_proof():
    result = reconcile_auksjonen_snapshot(queue(), snapshot())
    row = result["daily_batch"][0]
    assert row["stock_confidence"] == "UNVERIFIED"
    assert row["source_status_evidence"]["captured_at"].startswith("2026-09-17")
    assert row["source_status_evidence"]["ends_at"].startswith("2026-09-22")
    assert result["counts"]["auksjonen_api_matched"] == 1


def test_explicit_source_ended_is_held_not_a_human_delete():
    result = reconcile_auksjonen_snapshot(queue(), snapshot(status="SOLD"))
    assert result["review_queue"] == result["daily_batch"] == []
    assert result["held_separately"][0]["reason"] == "SOURCE_REPORTED_ENDED_NOT_OPERATOR_DELETE"
    assert result["counts"]["auksjonen_api_explicit_ended_held"] == 1
    assert "operator_deleted" not in result["counts"]


def test_expired_timestamp_disagreement_stays_uncertain():
    result = reconcile_auksjonen_snapshot(queue(), snapshot(ends="2026-09-16T00:00:00Z"))
    assert result["daily_batch"][0]["stock_confidence"] == "UNVERIFIED"
    assert result["counts"]["auksjonen_api_endtime_conflicts"] == 1
    assert "END_TIME_PASSED" in result["daily_batch"][0]["source_status_note"]


def test_missing_listing_and_future_source_snapshot_never_infer_ended():
    no_match = snapshot()
    no_match["listings"] = []
    result = reconcile_auksjonen_snapshot(queue(), no_match)
    assert result["counts"]["auksjonen_missing_from_bounded_snapshot"] == 1
    assert result["counts"]["direct_waiting_for_review"] == 1
    newer = snapshot()
    newer["captured_at"] = "2026-09-18T00:00:00Z"
    result = reconcile_auksjonen_snapshot(queue(), newer)
    assert result["counts"]["auksjonen_snapshot_status"] == "INVALID_OR_NEWER_THAN_REPORT"
    assert "source_status_evidence" not in result["review_queue"][0]


def test_host_spoofed_source_url_cannot_attach_evidence():
    deceptive = snapshot()
    deceptive["listings"][0]["url"] = "https://evil-auksjonen.no/auksjon/torget/Sko_Parti/572303"
    result = reconcile_auksjonen_snapshot(queue(), deceptive)
    assert result["counts"]["auksjonen_missing_from_bounded_snapshot"] == 1
    assert result["review_queue"][0]["stock_confidence"] == "UNVERIFIED"
