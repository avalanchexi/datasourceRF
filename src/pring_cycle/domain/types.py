from __future__ import annotations

from enum import StrEnum
from typing import NewType


class FormalStage(StrEnum):
    """A formal Stage I–VI produced only by the three core asset states."""

    STAGE_I = "stage_i"
    STAGE_II = "stage_ii"
    STAGE_III = "stage_iii"
    STAGE_IV = "stage_iv"
    STAGE_V = "stage_v"
    STAGE_VI = "stage_vi"


class CoreAssetState(StrEnum):
    """The stable bull or bear state of one core price barometer."""

    BULL = "bull"
    BEAR = "bear"


EvidenceObservationId = NewType("EvidenceObservationId", str)
ModelVersionId = NewType("ModelVersionId", str)
ProjectionSetId = NewType("ProjectionSetId", str)
RunId = NewType("RunId", str)
ReportId = NewType("ReportId", str)
