"""Framework-free boundary types for the Pring domain."""

from pring_cycle.domain.stage import StageResult, derive_formal_stage
from pring_cycle.domain.trend import PricePoint, TrendResult, TrendRules, evaluate_trend
from pring_cycle.domain.types import (
    CoreAssetState,
    EvidenceObservationId,
    FormalStage,
    ModelVersionId,
    ProjectionSetId,
    ReportId,
    RunId,
)

__all__ = [
    "CoreAssetState",
    "EvidenceObservationId",
    "FormalStage",
    "ModelVersionId",
    "ProjectionSetId",
    "ReportId",
    "RunId",
    "PricePoint",
    "StageResult",
    "TrendResult",
    "TrendRules",
    "derive_formal_stage",
    "evaluate_trend",
]
