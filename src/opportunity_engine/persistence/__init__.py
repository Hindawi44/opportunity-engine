"""Durable persistence boundary for opportunity state."""

from .database import (
    DEFAULT_DATABASE_URL,
    build_alembic_config,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from .lifecycle_models import LifecycleEventModel
from .lifecycle_repository import (
    LIFECYCLE_REASON_CODE_KEY,
    LifecycleEventRepository,
    LifecycleSnapshot,
)
from .live_unified_persistence import (
    ERROR_FILENAME as UNIFIED_PERSISTENCE_ERROR_FILENAME,
    PIPELINE_NAME as UNIFIED_PERSISTENCE_PIPELINE_NAME,
    SUMMARY_FILENAME as UNIFIED_PERSISTENCE_SUMMARY_FILENAME,
    UnifiedPersistenceExecutionError,
    persist_unified_report_file,
    persist_unified_report_with_artifacts,
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
    "LIFECYCLE_REASON_CODE_KEY",
    "LifecycleEventModel",
    "LifecycleEventRepository",
    "LifecycleSnapshot",
    "OPERATIONAL_PERSISTENCE_PIPELINE_NAME",
    "OperationalPersistenceError",
    "OpportunityModel",
    "OpportunityRepository",
    "PersistenceError",
    "ShipmentEvidenceTaskModel",
    "SourceRunModel",
    "StatusHistoryModel",
    "UNIFIED_PERSISTENCE_ERROR_FILENAME",
    "UNIFIED_PERSISTENCE_PIPELINE_NAME",
    "UNIFIED_PERSISTENCE_SUMMARY_FILENAME",
    "UNIFIED_REPORT_SCHEMA_VERSION",
    "UNIFIED_WORKFLOW_ENTITY_TYPE",
    "UnifiedOpportunityEvidenceModel",
    "UnifiedOpportunityModel",
    "UnifiedOpportunityRepository",
    "UnifiedPersistenceExecutionError",
    "UnifiedReportPersistenceError",
    "build_alembic_config",
    "create_database_engine",
    "create_session_factory",
    "persist_operational_snapshots",
    "persist_unified_opportunity_report",
    "persist_unified_report_file",
    "persist_unified_report_with_artifacts",
    "session_scope",
    "upgrade_database",
]
