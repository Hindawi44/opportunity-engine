"""Repository boundary for independent domain market signals."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from opportunity_engine.market_intelligence import MarketSignalRecord

from .market_signal_models import MarketSignalModel, MarketSignalObservationModel
from .models import utc_now
from .repository import PersistenceError


def _utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise PersistenceError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _state_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    state = deepcopy(dict(payload))
    state.pop("first_observed_at", None)
    state.pop("latest_observed_at", None)
    state.pop("observed_at", None)
    return state


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class MarketSignalRepository:
    """Transaction-scoped storage for latest signals and changed observations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_signal(self, signal: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(signal, Mapping):
            raise PersistenceError("market signal must be an object")
        raw = deepcopy(dict(signal))
        try:
            canonical = MarketSignalRecord.model_validate(raw)
        except ValidationError as exc:
            raise PersistenceError(f"invalid market signal: {exc}") from exc

        payload = canonical.model_dump(mode="json")
        state_hash = _payload_hash(_state_payload(payload))
        first_seen = _utc(canonical.first_observed_at, "first_observed_at")
        last_seen = _utc(canonical.latest_observed_at, "latest_observed_at")
        model = self.session.scalar(
            select(MarketSignalModel).where(
                MarketSignalModel.signal_id == canonical.signal_id
            )
        )
        created = model is None
        previous_hash = None if model is None else model.state_hash

        if model is None:
            model = MarketSignalModel(
                signal_id=canonical.signal_id,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
            )
            self.session.add(model)
        else:
            model.first_seen_at = min(_utc(model.first_seen_at, "first_seen_at"), first_seen)
            model.last_seen_at = max(_utc(model.last_seen_at, "last_seen_at"), last_seen)

        merged_first_seen = _utc(model.first_seen_at, "first_seen_at")
        merged_last_seen = _utc(model.last_seen_at, "last_seen_at")
        payload["first_observed_at"] = merged_first_seen.isoformat()
        payload["latest_observed_at"] = merged_last_seen.isoformat()
        payload["observed_at"] = merged_last_seen.isoformat()

        changed = created or previous_hash != state_hash
        model.signal_type = canonical.signal_type.value
        model.source_provider = canonical.source
        model.source_country = canonical.source_country
        model.source_url = str(canonical.source_url)
        model.title = canonical.title
        model.company_name = canonical.company_name
        model.seller_name = canonical.seller_name
        model.location = canonical.location
        model.event_date = canonical.event_date
        model.confidence = canonical.confidence
        model.related_opportunity_id = canonical.related_opportunity_id
        model.status = canonical.status.value
        model.state_hash = state_hash
        model.payload_json = payload
        model.updated_at = utc_now()
        self.session.flush()

        observation_created = False
        if changed:
            observation_key = sha256(
                f"{canonical.signal_id}:{state_hash}".encode("utf-8")
            ).hexdigest()
            existing = self.session.scalar(
                select(MarketSignalObservationModel).where(
                    MarketSignalObservationModel.observation_key == observation_key
                )
            )
            if existing is None:
                self.session.add(
                    MarketSignalObservationModel(
                        observation_key=observation_key,
                        signal_id=canonical.signal_id,
                        state_hash=state_hash,
                        observed_at=last_seen,
                        payload_json=payload,
                    )
                )
                observation_created = True
                self.session.flush()

        return {
            "signal_id": canonical.signal_id,
            "created": created,
            "changed": changed and not created,
            "observation_created": observation_created,
            "state_hash": state_hash,
        }

    def get(self, signal_id: str) -> MarketSignalModel | None:
        normalized = str(signal_id).strip()
        if not normalized:
            raise PersistenceError("signal_id must be a non-empty string")
        return self.session.scalar(
            select(MarketSignalModel).where(MarketSignalModel.signal_id == normalized)
        )

    def list_current(self) -> list[MarketSignalModel]:
        return list(
            self.session.scalars(
                select(MarketSignalModel).order_by(
                    MarketSignalModel.source_country,
                    MarketSignalModel.signal_id,
                )
            )
        )

    def list_observations(self, signal_id: str) -> list[MarketSignalObservationModel]:
        normalized = str(signal_id).strip()
        if not normalized:
            raise PersistenceError("signal_id must be a non-empty string")
        return list(
            self.session.scalars(
                select(MarketSignalObservationModel)
                .where(MarketSignalObservationModel.signal_id == normalized)
                .order_by(MarketSignalObservationModel.id)
            )
        )
