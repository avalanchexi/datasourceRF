"""Public component checks using full admitted model identities.

This helper returns actual projection and selection results; it does not evaluate
complete replay coverage, aggregate differences or persist a replay output.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelection, select_retrieval_input


@dataclass(frozen=True)
class PublicContextCheck:
    context: ContextProjection
    selection: ModelInputSelection


def check_public_context(
    paths: RuntimePaths,
    manifest: dict[str, Any],
    *,
    metric_ids: tuple[str, ...],
    day: str,
    period: str | None = None,
) -> PublicContextCheck:
    cutoff = datetime.fromisoformat(day + "T23:59:59.999999+08:00")
    context = project_public_context(paths, manifest, day=day)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date=day,
        client_request_id=f"public-component-{uuid4().hex}",
        model_version_id=manifest["model_version_id"],
        system_as_of=cutoff,
        release_event_id="synthetic:public-component",
        metric_ids=metric_ids,
        period=period or day,
    )
    return PublicContextCheck(context, select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC))


def project_public_context(
    paths: RuntimePaths, manifest: dict[str, Any], *, day: str
) -> ContextProjection:
    return build_context_projection(
        EvidenceRepository(paths.database),
        model_manifest=manifest,
        target_business_date=day,
        as_of=datetime.fromisoformat(day + "T23:59:59.999999+08:00"),
        as_of_mode=AsOfMode.PUBLIC,
        persist_derived=False,
    )
