"""Stable, conservative market-profile contracts.

A market profile identifies language, currency, source registries, and the policy
references needed by later tax, customs, logistics, risk, and qualification
engines. V1 is deliberately descriptive: it does not calculate tax, customs, or
transport and it never changes an opportunity decision.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


SCHEMA_VERSION = "market-profile-v1"
_ALLOWED_TRANSACTION_SCOPES = frozenset({"DOMESTIC", "CROSS_BORDER"})
_ALLOWED_SOURCE_STATUSES = frozenset(
    {"ACTIVE", "BLOCKED_AUTH", "CODE_READY", "DEPRECATED", "PLANNED"}
)
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")


class MarketProfileError(ValueError):
    """Raised when a market profile or its source registries are inconsistent."""


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object and reject missing, invalid, or non-object payloads."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MarketProfileError(f"required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MarketProfileError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MarketProfileError(f"JSON root must be an object: {path}")
    return payload


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketProfileError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise MarketProfileError(f"{field_name} must be a non-empty list")
    items = tuple(_non_empty(item, f"{field_name}[]") for item in value)
    if len(set(items)) != len(items):
        raise MarketProfileError(f"{field_name} must not contain duplicates")
    return items


def _object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MarketProfileError(f"{field_name} must be an object")
    return deepcopy(value)


def _repo_relative_json_path(value: object, field_name: str) -> str:
    text = _non_empty(value, field_name)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".json":
        raise MarketProfileError(f"{field_name} must be a repository-relative JSON path")
    return text


def _require_bool(mapping: dict[str, Any], key: str, expected: bool) -> None:
    if mapping.get(key) is not expected:
        raise MarketProfileError(f"{key} must be {str(expected).lower()}")


def _reject_embedded_rates(policy: dict[str, Any], field_name: str) -> None:
    forbidden = sorted(
        key
        for key in policy
        if key.casefold().endswith(("_rate", "_percent", "_percentage"))
    )
    if forbidden:
        raise MarketProfileError(
            f"{field_name} must reference rules rather than embed mutable rates: "
            + ", ".join(forbidden)
        )


@dataclass(frozen=True, slots=True)
class MarketProfileV1:
    """Source-agnostic market configuration boundary for later engines."""

    profile_id: str
    market_code: str
    market_name: str
    currency_code: str
    language_codes: tuple[str, ...]
    fallback_language_codes: tuple[str, ...]
    transaction_scope: str
    source_registry: dict[str, Any]
    tax_policy: dict[str, Any]
    customs_policy: dict[str, Any]
    logistics_policy: dict[str, Any]
    risk_policy: dict[str, Any]
    qualification_policy: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise MarketProfileError(f"schema_version must be {SCHEMA_VERSION}")
        _non_empty(self.profile_id, "profile_id")
        if _COUNTRY_CODE.fullmatch(self.market_code) is None:
            raise MarketProfileError("market_code must be a two-letter uppercase code")
        _non_empty(self.market_name, "market_name")
        if _CURRENCY_CODE.fullmatch(self.currency_code) is None:
            raise MarketProfileError("currency_code must be a three-letter uppercase code")
        if not self.language_codes:
            raise MarketProfileError("language_codes must not be empty")
        for code in (*self.language_codes, *self.fallback_language_codes):
            if _LANGUAGE_CODE.fullmatch(code) is None:
                raise MarketProfileError(f"invalid language code: {code}")
        if set(self.language_codes) & set(self.fallback_language_codes):
            raise MarketProfileError("primary and fallback language codes must not overlap")
        if self.transaction_scope not in _ALLOWED_TRANSACTION_SCOPES:
            raise MarketProfileError(
                f"transaction_scope must be one of {sorted(_ALLOWED_TRANSACTION_SCOPES)}"
            )

        market_name = _non_empty(self.source_registry.get("market_name"), "source_registry.market_name")
        if market_name != self.market_name:
            raise MarketProfileError("source_registry.market_name must match market_name")
        _repo_relative_json_path(
            self.source_registry.get("plan_path"), "source_registry.plan_path"
        )
        _repo_relative_json_path(
            self.source_registry.get("runtime_status_path"),
            "source_registry.runtime_status_path",
        )
        channels = _string_tuple(
            self.source_registry.get("signal_channels"),
            "source_registry.signal_channels",
        )
        if tuple(self.source_registry.get("signal_channels", ())) != channels:
            raise MarketProfileError("source_registry.signal_channels must be normalized")
        _require_bool(
            self.source_registry,
            "qualification_requires_verified_sale_listing",
            True,
        )

        for name, policy in (
            ("tax_policy", self.tax_policy),
            ("customs_policy", self.customs_policy),
            ("logistics_policy", self.logistics_policy),
        ):
            _non_empty(policy.get("profile_id"), f"{name}.profile_id")
            _non_empty(policy.get("mode"), f"{name}.mode")
            _require_bool(policy, "calculation_enabled", False)
            _reject_embedded_rates(policy, name)

        if self.transaction_scope == "DOMESTIC":
            _require_bool(
                self.customs_policy,
                "cross_border_import_supported",
                False,
            )

        default_level = _non_empty(
            self.risk_policy.get("default_level"), "risk_policy.default_level"
        )
        allowed_levels = _string_tuple(
            self.risk_policy.get("allowed_levels"), "risk_policy.allowed_levels"
        )
        if default_level not in allowed_levels:
            raise MarketProfileError("risk_policy.default_level must be allowed")
        _require_bool(
            self.risk_policy,
            "source_failure_is_not_zero_opportunities",
            True,
        )
        _require_bool(
            self.risk_policy,
            "unknown_costs_block_qualification",
            True,
        )

        _non_empty(
            self.qualification_policy.get("listing_status_required"),
            "qualification_policy.listing_status_required",
        )
        _non_empty(
            self.qualification_policy.get("verification_status_required"),
            "qualification_policy.verification_status_required",
        )
        _string_tuple(
            self.qualification_policy.get("minimum_evidence"),
            "qualification_policy.minimum_evidence",
        )
        _require_bool(
            self.qualification_policy,
            "automatic_purchase_allowed",
            False,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MarketProfileV1":
        """Build and validate a profile from a JSON object."""
        required = {
            "schema_version",
            "profile_id",
            "market_code",
            "market_name",
            "currency_code",
            "language_codes",
            "fallback_language_codes",
            "transaction_scope",
            "source_registry",
            "tax_policy",
            "customs_policy",
            "logistics_policy",
            "risk_policy",
            "qualification_policy",
        }
        missing = sorted(required - payload.keys())
        extra = sorted(payload.keys() - required)
        if missing:
            raise MarketProfileError("missing profile fields: " + ", ".join(missing))
        if extra:
            raise MarketProfileError("unsupported profile fields: " + ", ".join(extra))
        return cls(
            schema_version=_non_empty(payload["schema_version"], "schema_version"),
            profile_id=_non_empty(payload["profile_id"], "profile_id"),
            market_code=_non_empty(payload["market_code"], "market_code"),
            market_name=_non_empty(payload["market_name"], "market_name"),
            currency_code=_non_empty(payload["currency_code"], "currency_code"),
            language_codes=_string_tuple(payload["language_codes"], "language_codes"),
            fallback_language_codes=_string_tuple(
                payload["fallback_language_codes"], "fallback_language_codes"
            ),
            transaction_scope=_non_empty(
                payload["transaction_scope"], "transaction_scope"
            ),
            source_registry=_object(payload["source_registry"], "source_registry"),
            tax_policy=_object(payload["tax_policy"], "tax_policy"),
            customs_policy=_object(payload["customs_policy"], "customs_policy"),
            logistics_policy=_object(payload["logistics_policy"], "logistics_policy"),
            risk_policy=_object(payload["risk_policy"], "risk_policy"),
            qualification_policy=_object(
                payload["qualification_policy"], "qualification_policy"
            ),
        )

    @classmethod
    def from_path(cls, path: Path) -> "MarketProfileV1":
        return cls.from_dict(load_json_object(path))

    def to_dict(self) -> dict[str, Any]:
        """Return a detached, JSON-ready profile payload."""
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "market_code": self.market_code,
            "market_name": self.market_name,
            "currency_code": self.currency_code,
            "language_codes": list(self.language_codes),
            "fallback_language_codes": list(self.fallback_language_codes),
            "transaction_scope": self.transaction_scope,
            "source_registry": deepcopy(self.source_registry),
            "tax_policy": deepcopy(self.tax_policy),
            "customs_policy": deepcopy(self.customs_policy),
            "logistics_policy": deepcopy(self.logistics_policy),
            "risk_policy": deepcopy(self.risk_policy),
            "qualification_policy": deepcopy(self.qualification_policy),
        }


def build_market_profile_snapshot(
    profile: MarketProfileV1,
    source_plan: dict[str, Any],
    source_gap_matrix: dict[str, Any],
) -> dict[str, Any]:
    """Resolve a profile against the existing authoritative source registries."""
    markets = source_plan.get("markets")
    if not isinstance(markets, list):
        raise MarketProfileError("source plan markets must be a list")
    planned_market = next(
        (
            item
            for item in markets
            if isinstance(item, dict) and item.get("market") == profile.market_name
        ),
        None,
    )
    if planned_market is None:
        raise MarketProfileError(
            f"market not found in source plan: {profile.market_name}"
        )
    planned_sources = planned_market.get("sources")
    if not isinstance(planned_sources, list) or not planned_sources:
        raise MarketProfileError("planned market must contain sources")

    planned_by_name: dict[str, dict[str, Any]] = {}
    for row in planned_sources:
        if not isinstance(row, dict):
            raise MarketProfileError("planned source rows must be objects")
        name = _non_empty(row.get("source"), "planned source name")
        if name in planned_by_name:
            raise MarketProfileError(f"duplicate planned source: {name}")
        planned_by_name[name] = row

    runtime_sources = source_gap_matrix.get("sources")
    if not isinstance(runtime_sources, list):
        raise MarketProfileError("source gap matrix sources must be a list")
    runtime_by_name: dict[str, dict[str, Any]] = {}
    for row in runtime_sources:
        if not isinstance(row, dict) or row.get("market") != profile.market_name:
            continue
        name = _non_empty(row.get("source"), "runtime source name")
        if name in runtime_by_name:
            raise MarketProfileError(f"duplicate runtime source: {name}")
        runtime_by_name[name] = row

    planned_names = set(planned_by_name)
    runtime_names = set(runtime_by_name)
    if planned_names != runtime_names:
        missing_runtime = sorted(planned_names - runtime_names)
        unplanned_runtime = sorted(runtime_names - planned_names)
        details = []
        if missing_runtime:
            details.append("missing runtime: " + ", ".join(missing_runtime))
        if unplanned_runtime:
            details.append("unplanned runtime: " + ", ".join(unplanned_runtime))
        raise MarketProfileError("source registry drift: " + "; ".join(details))

    allowed_statuses = source_gap_matrix.get("allowed_statuses")
    if not isinstance(allowed_statuses, list):
        raise MarketProfileError("source gap matrix allowed_statuses must be a list")
    if set(allowed_statuses) != _ALLOWED_SOURCE_STATUSES:
        raise MarketProfileError("source gap matrix status vocabulary is incompatible")

    observed_channels: set[str] = set()
    sources: list[dict[str, Any]] = []
    status_counts = {status: 0 for status in sorted(_ALLOWED_SOURCE_STATUSES)}
    for name, planned in planned_by_name.items():
        runtime = runtime_by_name[name]
        planned_channel = planned.get("channel")
        runtime_channel = runtime.get("channel")
        if planned_channel != runtime_channel:
            raise MarketProfileError(f"channel drift for source: {name}")
        if isinstance(planned_channel, str) and planned_channel:
            observed_channels.add(planned_channel)

        status = _non_empty(runtime.get("status"), f"runtime status for {name}")
        if status not in _ALLOWED_SOURCE_STATUSES:
            raise MarketProfileError(f"unsupported source status for {name}: {status}")
        status_counts[status] += 1
        sources.append(
            {
                "source": name,
                "priority": planned.get("priority"),
                "channel": planned_channel,
                "qualification_mode": (
                    "SIGNAL_ONLY"
                    if planned_channel in profile.source_registry["signal_channels"]
                    else "REQUIRES_RECORD_VERIFICATION"
                ),
                "declared_status": planned.get("audit_status"),
                "runtime_status": status,
                "fetched": int(runtime.get("fetched") or 0),
                "access_mode": runtime.get("access_mode"),
                "required_configuration": list(
                    runtime.get("required_configuration") or []
                ),
                "error": runtime.get("error"),
            }
        )

    declared_channels = set(profile.source_registry["signal_channels"])
    if observed_channels != declared_channels:
        raise MarketProfileError(
            "signal channel drift: declared="
            + ",".join(sorted(declared_channels))
            + " observed="
            + ",".join(sorted(observed_channels))
        )

    sources.sort(key=lambda row: (row.get("priority") is None, row.get("priority"), row["source"]))
    return {
        **profile.to_dict(),
        "source_registry_snapshot": {
            "generated_at": source_gap_matrix.get("generated_at"),
            "source_count": len(sources),
            "status_counts": status_counts,
            "sources": sources,
        },
        "safety": {
            "calculates_tax": False,
            "calculates_customs": False,
            "calculates_logistics": False,
            "changes_final_decision": False,
            "automatic_purchase": False,
        },
    }
