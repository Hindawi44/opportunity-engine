"""Repository for durable Swedish organisation identity watches."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .sweden_organisation_watchlist_models import (
    SwedenOrganisationWatchlistModel,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SwedenOrganisationIdentity:
    organisation_number: str
    company_name: str
    artifact_company_name: str
    source_provider: str
    source_url: str
    first_seen_at: datetime
    last_seen_at: datetime
    verified_at: datetime
    payload: dict[str, Any]


class SwedenOrganisationWatchlistRepository:
    """Read and upsert verified identities without creating market signals."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _identity(
        model: SwedenOrganisationWatchlistModel,
    ) -> SwedenOrganisationIdentity:
        return SwedenOrganisationIdentity(
            organisation_number=model.organisation_number,
            company_name=model.company_name,
            artifact_company_name=model.artifact_company_name,
            source_provider=model.source_provider,
            source_url=model.source_url,
            first_seen_at=_utc(model.first_seen_at),
            last_seen_at=_utc(model.last_seen_at),
            verified_at=_utc(model.verified_at),
            payload=dict(model.payload_json or {}),
        )

    def upsert(
        self,
        identity: SwedenOrganisationIdentity,
    ) -> SwedenOrganisationIdentity:
        model = self._session.get(
            SwedenOrganisationWatchlistModel,
            identity.organisation_number,
        )
        if model is None:
            model = SwedenOrganisationWatchlistModel(
                organisation_number=identity.organisation_number,
                company_name=identity.company_name,
                artifact_company_name=identity.artifact_company_name,
                source_provider=identity.source_provider,
                source_url=identity.source_url,
                payload_json=dict(identity.payload),
                first_seen_at=_utc(identity.first_seen_at),
                last_seen_at=_utc(identity.last_seen_at),
                verified_at=_utc(identity.verified_at),
            )
            self._session.add(model)
        else:
            model.company_name = identity.company_name
            model.artifact_company_name = identity.artifact_company_name
            model.source_provider = identity.source_provider
            model.source_url = identity.source_url
            model.payload_json = dict(identity.payload)
            model.last_seen_at = max(
                _utc(model.last_seen_at),
                _utc(identity.last_seen_at),
            )
            model.verified_at = max(
                _utc(model.verified_at),
                _utc(identity.verified_at),
            )
        self._session.flush()
        return self._identity(model)

    def list_identities(
        self,
        *,
        limit: int = 50,
    ) -> list[SwedenOrganisationIdentity]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        statement = (
            select(SwedenOrganisationWatchlistModel)
            .order_by(
                SwedenOrganisationWatchlistModel.last_seen_at.desc(),
                SwedenOrganisationWatchlistModel.organisation_number.asc(),
            )
            .limit(limit)
        )
        return [
            self._identity(model)
            for model in self._session.scalars(statement).all()
        ]
