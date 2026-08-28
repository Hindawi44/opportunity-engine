from opportunity_engine.discovery import market_fit_evidence_v1 as market_fit
from opportunity_engine.discovery import search_provenance_integrity_v1 as provenance


def test_provenance_integrity_hook_is_inside_final_wrapper_chain_without_new_runtime() -> None:
    # Market-Fit is intentionally installed later and is the public outer wrapper.
    # Prove provenance remains its direct upstream behavior instead of requiring
    # the public function object itself to equal the inner provenance wrapper.
    assert market_fit._UPSTREAM_VERIFY_REPORT is provenance._verify_with_query_and_recovery_provenance
    assert market_fit._UPSTREAM_TOP5_GATE is provenance._top5_with_truthful_provenance
    assert provenance.SEARCH_REQUESTS_ADDED == 0
    assert provenance.PAGE_FETCHES_ADDED == 0
