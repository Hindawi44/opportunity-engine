"""Durable persistence boundary for opportunity state."""

from .database import (
    DEFAULT_DATABASE_URL,
    build_alembic_config,
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from .human_review import (
    HumanReviewOutcome,
    HumanReviewOutcomeRepository,
    apply_human_review_outcome,
    apply_persisted_human_review,
)
from .human_review_models import HumanReviewOutcomeModel
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
from .market_signal_models import MarketSignalModel, MarketSignalObservationModel
from .market_signal_repository import MarketSignalRepository
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
    "HumanReviewOutcome",
    "HumanReviewOutcomeModel",
    "HumanReviewOutcomeRepository",
    "LIFECYCLE_REASON_CODE_KEY",
    "LifecycleEventModel",
    "LifecycleEventRepository",
    "LifecycleSnapshot",
    "MarketSignalModel",
    "MarketSignalObservationModel",
    "MarketSignalRepository",
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
    "apply_human_review_outcome",
    "apply_persisted_human_review",
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
