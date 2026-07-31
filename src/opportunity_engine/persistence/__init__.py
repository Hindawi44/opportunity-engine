"""Durable persistence boundary for opportunity state."""

from .database import (
    DEFAULT_DATABASE_URL,
    build_alembic_config,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from .models import (
    Base,
    OpportunityModel,
    ShipmentEvidenceTaskModel,
    SourceRunModel,
    StatusHistoryModel,
)
from .operational_adapter import (
    PIPELINE_NAME as OPERATIONAL_PERSISTENCE_PIPELINE_NAME,
    OperationalPersistenceError,
    persist_operational_snapshots,
)
from .repository import OpportunityRepository, PersistenceError

__all__ = [
    "Base",
    "DEFAULT_DATABASE_URL",
    "OPERATIONAL_PERSISTENCE_PIPELINE_NAME",
    "OperationalPersistenceError",
    "OpportunityModel",
    "OpportunityRepository",
    "PersistenceError",
    "ShipmentEvidenceTaskModel",
    "SourceRunModel",
    "StatusHistoryModel",
    "build_alembic_config",
    "create_database_engine",
    "create_session_factory",
    "persist_operational_snapshots",
    "session_scope",
    "upgrade_database",
]
