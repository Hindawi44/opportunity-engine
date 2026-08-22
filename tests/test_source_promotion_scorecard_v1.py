from __future__ import annotations

from opportunity_engine.source_promotion_scorecard import build_source_promotion_scorecard


SOURCE_CANDIDATES = {
    "source_candidates": [
        {
            "source_domain": "joblot.stocklear.eu",
            "source_name": "Stocklear",
            "verified_opportunity_count": 2,
            "status": "VALIDATED_SOURCE",
            "shadow_eligible": True,
            "production_active": False,
        }
    ]
}

LIVE_PROOF = {
    "verified_new_opportunities": [
        {
            "source_domain": "joblot.stocklear.eu",
            "source_url": f"https://joblot.stocklear.eu/auction/{auction}/",
            "source_page_verified": True,
            "teaching_url": False,
            "shadow_only": True,
            "production_active": False,
        }
        for auction in (21656, 21777, 21780, 21786, 21820)
    ],
    "production_mutation": False,
    "automatic_promotion": False,
}

ACCESS_PROOF = {
    "source_domain": "joblot.stocklear.eu",
    "round_count": 3,
    "total_public_get_requests": 18,
    "total_usable_public_samples": 18,
    "usable_public_ratio": 1.0,
    "blocked_403_count": 0,
    "rate_limited_429_count": 0,
    "challenge_count": 0,
    "login_redirect_count": 0,
    "html_drift_count": 0,
    "verdict": "PUBLIC_ACCESS_STABLE_PARTIAL",
    "safety": {"production_mutation": False, "automatic_promotion": False},
}


def _score(*, rounds: int, live_proof=LIVE_PROOF, access_proof=ACCESS_PROOF, candidates: int = 5):
    return build_source_promotion_scorecard(
        SOURCE_CANDIDATES,
        live_proof,
        access_proof,
        source_domain="joblot.stocklear.eu",
        independent_live_discovery_rounds=rounds,
        live_source_candidate_count=candidates,
    )


def test_one_live_discovery_round_cannot_promote_even_with_high_score() -> None:
    report = _score(rounds=1)

    assert report["promotion_readiness_score"] >= 90
    assert report["metrics"]["verification_yield"] == 1.0
    assert report["metrics"]["false_positive_count"] == 0
    assert report["metrics"]["false_positive_rate"] == 0.0
    assert report["decision"] == "KEEP_SHADOW"
    assert "NEEDS_SECOND_INDEPENDENT_LIVE_DISCOVERY_ROUND" in report["blocking_reasons"]
    assert report["production_active"] is False
    assert report["automatic_promotion"] is False


def test_two_independent_rounds_can_recommend_promotion_without_activating() -> None:
    report = _score(rounds=2)

    assert report["decision"] == "PROMOTE_CANDIDATE"
    assert report["blocking_reasons"] == []
    assert report["production_active"] is False
    assert report["promotion_requires_explicit_approval"] is True
    assert report["automatic_promotion"] is False


def test_access_instability_is_a_hard_blocker() -> None:
    unstable = dict(ACCESS_PROOF)
    unstable["rate_limited_429_count"] = 1
    unstable["usable_public_ratio"] = 17 / 18

    report = _score(rounds=2, access_proof=unstable)

    assert report["decision"] == "KEEP_SHADOW"
    assert "ACCESS_NOT_STABLE" in report["blocking_reasons"]


def test_teaching_url_recovery_is_a_hard_blocker() -> None:
    contaminated = {**LIVE_PROOF, "verified_new_opportunities": [dict(row) for row in LIVE_PROOF["verified_new_opportunities"]]}
    contaminated["verified_new_opportunities"][0]["teaching_url"] = True

    report = _score(rounds=2, live_proof=contaminated)

    assert report["decision"] == "KEEP_SHADOW"
    assert "NOVELTY_CONTAMINATED_BY_TEACHING_URL" in report["blocking_reasons"]


def test_unverified_recovery_does_not_count_and_increases_false_positive_rate() -> None:
    weak = {**LIVE_PROOF, "verified_new_opportunities": [dict(row) for row in LIVE_PROOF["verified_new_opportunities"]]}
    weak["verified_new_opportunities"][0]["source_page_verified"] = False

    report = _score(rounds=2, live_proof=weak)

    assert report["metrics"]["verified_new_opportunity_count"] == 4
    assert report["metrics"]["false_positive_count"] == 1
    assert report["metrics"]["false_positive_rate"] == 0.2


def test_config_or_scorecard_never_activates_production() -> None:
    report = _score(rounds=99)

    assert report["production_active"] is False
    assert report["production_mutation"] is False
    assert report["automatic_source_addition"] is False
    assert report["automatic_promotion"] is False
