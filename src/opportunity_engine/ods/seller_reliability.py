"""Conservative seller reliability assessment from source-provided facts only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SellerReliabilityReport:
    seller_id: str | None
    seller_name: str | None
    seller_type: str | None
    score: float | None
    grade: str
    risk: str
    risk_label: str
    confidence: str
    is_verified: bool
    evidence_count: int
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


class SellerReliabilityEngine:
    """Score a seller without inventing missing profile or reputation data."""

    def assess(self, metadata: Mapping[str, Any]) -> SellerReliabilityReport:
        seller_id = _clean(metadata.get("seller_id") or metadata.get("vendor_id"))
        seller_name = _clean(metadata.get("seller_name") or metadata.get("vendor_name"))
        seller_type = _clean(metadata.get("seller_type") or metadata.get("vendor_type"))
        verified = _as_bool(metadata.get("seller_verified") or metadata.get("verified_seller"))
        rating = _bounded_float(metadata.get("seller_rating"), 0.0, 5.0)
        review_count = _non_negative_int(metadata.get("seller_review_count") or metadata.get("review_count"))
        account_age_days = _non_negative_int(metadata.get("seller_account_age_days") or metadata.get("account_age_days"))
        listing_count = _non_negative_int(metadata.get("seller_listing_count") or metadata.get("listing_count"))
        relist_count = _non_negative_int(metadata.get("seller_relist_count") or metadata.get("relist_count"))

        evidence = [seller_id, seller_name, seller_type, verified, rating, review_count, account_age_days, listing_count, relist_count]
        evidence_count = sum(value is not None for value in evidence)
        reasons: list[str] = []
        warnings: list[str] = []

        if evidence_count == 0:
            return SellerReliabilityReport(
                seller_id=None,
                seller_name=None,
                seller_type=None,
                score=None,
                grade="U",
                risk="unknown",
                risk_label="⚪ بائع غير متحقق",
                confidence="insufficient",
                is_verified=False,
                evidence_count=0,
                reasons=("لا توجد بيانات بائع موثقة في المصدر.",),
                warnings=("Seller reliability cannot be assessed without source-provided seller facts.",),
            )

        score = 50.0
        if verified is True:
            score += 20
            reasons.append("هوية البائع موثقة في المصدر.")
        elif verified is False:
            score -= 10
            warnings.append("Seller is explicitly marked as unverified.")

        if rating is not None:
            score += (rating - 2.5) * 8
            reasons.append(f"تقييم البائع المتاح هو {rating:.1f}/5.")
        if review_count is not None:
            score += min(review_count, 50) * 0.2
        if account_age_days is not None:
            score += min(account_age_days / 365.0, 5.0) * 2
        if listing_count is not None:
            score += min(listing_count, 100) * 0.05
        if relist_count is not None:
            score -= min(relist_count, 10) * 3
            if relist_count >= 3:
                warnings.append("Repeated relisting may indicate stale inventory or unstable terms.")

        score = round(max(0.0, min(score, 100.0)), 2)
        confidence = "high" if evidence_count >= 6 else "medium" if evidence_count >= 3 else "low"
        grade = _grade(score)
        risk, label = _risk(score, confidence)
        if not reasons:
            reasons.append("التقييم مبني فقط على حقول البائع المتاحة في المصدر.")

        return SellerReliabilityReport(
            seller_id=seller_id,
            seller_name=seller_name,
            seller_type=seller_type,
            score=score,
            grade=grade,
            risk=risk,
            risk_label=label,
            confidence=confidence,
            is_verified=verified is True,
            evidence_count=evidence_count,
            reasons=tuple(reasons),
            warnings=tuple(warnings),
        )


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def _risk(score: float, confidence: str) -> tuple[str, str]:
    if confidence == "low":
        return "unknown", "⚪ ثقة بائع محدودة"
    if score >= 75:
        return "low", "🟢 مخاطر بائع منخفضة"
    if score >= 50:
        return "medium", "🟡 مخاطر بائع متوسطة"
    return "high", "🔴 مخاطر بائع مرتفعة"


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "yes", "1", "verified"}:
            return True
        if lowered in {"false", "no", "0", "unverified"}:
            return False
    return None


def _bounded_float(value: Any, minimum: float, maximum: float) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _non_negative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
