from opportunity_engine.discovery import clothing_inventory_search
from opportunity_engine.discovery import provider_unique_page_verification as verifier
from opportunity_engine.discovery import search_provenance_integrity_v1 as provenance


def test_provenance_integrity_hook_is_installed_without_new_runtime() -> None:
    assert verifier.verify_provider_unique_pages is provenance._verify_with_query_and_recovery_provenance
    assert (
        clothing_inventory_search.apply_post_verification_top5_hard_gate
        is provenance._top5_with_truthful_provenance
    )
    assert provenance.SEARCH_REQUESTS_ADDED == 0
    assert provenance.PAGE_FETCHES_ADDED == 0
