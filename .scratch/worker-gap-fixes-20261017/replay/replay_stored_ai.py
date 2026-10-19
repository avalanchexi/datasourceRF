"""Pass the 10-15 report's stored AI prose through the new report checks, no AI called.

The stored codex_cli document (report-0123080db982b28815a8) is rebuilt from its body; its
mechanical fields (bundle id, cutoff, core states, conclusions) are the new input's, which
the prompt has the AI copy as given. The prose is the AI's own, as stored.
"""
import json
import sys
from pathlib import Path

from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import (
    AdapterResponse,
    ReportInput,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from pring_cycle.runtime import RuntimePaths

paths = RuntimePaths.discover(Path("/tmp/pring-wg07-replay"))
projection = ProjectionSetRepository(paths.database).get("projection-6ff0cd3a7d71cbdfe8e4")
repository = ReportRepository(paths.database)
stored = repository.get("report-0123080db982b28815a8")
source = report_input_from_projection(projection)


class StoredProse:
    name = "codex_cli"
    version = "stored-2026-10-16"

    def generate(self, bundle: ReportInput) -> AdapterResponse:
        return AdapterResponse.succeeded(
            {
                "bundle_id": bundle.bundle_id,
                "current_stage": bundle.current_stage,
                "report_cutoff": bundle.report_cutoff.isoformat(),
                "core_states": bundle.core_states,
                "conclusions": bundle.conclusions,
                "proxy_used": False,
                "sections": stored.body["ai_explanation"],
            }
        )


result = ReportService(repository, (StoredProse(),)).generate(
    source, client_request_id="wg07-replay-stored-ai-1015"
)
snapshot = repository.get(result.report_snapshot_id)
rejections = [a.process_audit.get("rejection") for a in repository.attempts(result.report_snapshot_id)]
print(json.dumps({
    "report_snapshot_id": result.report_snapshot_id,
    "status": result.status,
    "prompt_version": snapshot.prompt_version,
    "explanation_source": snapshot.body.get("explanation_source"),
    "untranslated_codes": snapshot.body.get("untranslated_codes"),
    "rejections": rejections,
    "display_names": source.display_names,
}, ensure_ascii=False, indent=1, default=str))
