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
    UnifiedOpportunityEvidenceModel,
    UnifiedOpportunityModel,
)
from .operational_adapter import (
    PIPELINE_NAME as OPERATIONAL_PERSISTENCE_PIPELINE_NAME,
    OperationalPersistenceError,
    persist_operational_snapshots,
)
from .repository import OpportunityRepository, PersistenceError
from .unified_report_adapter import (
    UNIFIED_REPORT_SCHEMA_VERSION,
    UnifiedReportPersistenceError,
    persist_unified_opportunity_report,
)
from .unified_repository import (
    UNIFIED_WORKFLOW_ENTITY_TYPE,
    UnifiedOpportunityRepository,
)

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
    "UNIFIED_REPORT_SCHEMA_VERSION",
    "UNIFIED_WORKFLOW_ENTITY_TYPE",
    "UnifiedOpportunityEvidenceModel",
    "UnifiedOpportunityModel",
    "UnifiedOpportunityRepository",
    "UnifiedReportPersistenceError",
    "build_alembic_config",
    "create_database_engine",
    "create_session_factory",
    "persist_operational_snapshots",
    "persist_unified_opportunity_report",
    "session_scope",
    "upgrade_database",
]
