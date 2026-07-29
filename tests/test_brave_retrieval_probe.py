import pytest

from opportunity_engine.discovery.brave_retrieval_probe import (
    RetrievalProbeResult,
    classify_retrieval_probe,
)


def _result(probe_id, count=0, error=None):
    return RetrievalProbeResult(
        probe_id=probe_id,
        client="test",
        query=probe_id,
        result_count=count,
        error=error,
    )


def _probe_set(*, current=1, legacy=1, unscoped=1, scoped=1):
    return (
        _result("current-generic", current),
        _result("legacy-generic", legacy),
        _result("legacy-axl-unscoped", unscoped),
        _result("legacy-axl-site", scoped),
    )


def test_probe_detects_current_client_recall_regression():
    diagnosis = classify_retrieval_probe(
        _probe_set(current=0, legacy=4, unscoped=1, scoped=0)
    )
    assert diagnosis["diagnosis"] == "CURRENT_CLIENT_RECALL_REGRESSION"


def test_probe_detects_generic_zero_results_before_source_changes():
    diagnosis = classify_retrieval_probe(
        _probe_set(current=0, legacy=0, unscoped=0, scoped=0)
    )
    assert diagnosis["diagnosis"] == "GENERIC_SEARCH_ZERO_RESULTS"


def test_probe_detects_source_index_gap():
    diagnosis = classify_retrieval_probe(
        _probe_set(current=5, legacy=5, unscoped=0, scoped=0)
    )
    assert diagnosis["diagnosis"] == "SOURCE_NOT_RECALLED_BY_BRAVE"


def test_probe_detects_site_operator_recall_failure():
    diagnosis = classify_retrieval_probe(
        _probe_set(current=5, legacy=5, unscoped=2, scoped=0)
    )
    assert diagnosis["diagnosis"] == "SITE_OPERATOR_RECALL_FAILURE"


def test_probe_accepts_working_source_query_shape():
    diagnosis = classify_retrieval_probe(
        _probe_set(current=5, legacy=5, unscoped=2, scoped=1)
    )
    assert diagnosis["diagnosis"] == "SOURCE_QUERY_RECALLS_RESULTS"


def test_probe_fails_closed_when_a_required_probe_is_missing():
    with pytest.raises(ValueError, match="missing retrieval probes"):
        classify_retrieval_probe((_result("current-generic", 1),))
