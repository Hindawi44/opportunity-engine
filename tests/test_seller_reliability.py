from opportunity_engine.ods.seller_reliability import SellerReliabilityEngine


def test_verified_established_seller_scores_high() -> None:
    report = SellerReliabilityEngine().assess(
        {
            "seller_id": "seller-1",
            "seller_name": "Asset Partner AS",
            "seller_type": "company",
            "seller_verified": True,
            "seller_rating": 4.8,
            "seller_review_count": 40,
            "seller_account_age_days": 1600,
            "seller_listing_count": 75,
            "seller_relist_count": 0,
        }
    )

    assert report.score is not None
    assert report.score >= 75
    assert report.grade in {"A", "B"}
    assert report.risk == "low"
    assert report.confidence == "high"
    assert report.is_verified is True


def test_missing_seller_data_remains_unknown() -> None:
    report = SellerReliabilityEngine().assess({})

    assert report.score is None
    assert report.grade == "U"
    assert report.risk == "unknown"
    assert report.confidence == "insufficient"
    assert report.evidence_count == 0


def test_relisting_and_unverified_status_increase_risk() -> None:
    report = SellerReliabilityEngine().assess(
        {
            "seller_id": "seller-2",
            "seller_verified": False,
            "seller_rating": 1.5,
            "seller_review_count": 3,
            "seller_relist_count": 7,
        }
    )

    assert report.score is not None
    assert report.score < 50
    assert report.risk == "high"
    assert report.warnings


def test_sparse_profile_has_low_confidence_without_fake_certainty() -> None:
    report = SellerReliabilityEngine().assess({"seller_name": "Unknown Seller"})

    assert report.score is not None
    assert report.confidence == "low"
    assert report.risk == "unknown"
    assert report.grade == "D"
