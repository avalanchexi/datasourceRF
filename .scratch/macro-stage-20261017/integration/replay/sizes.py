"""Report input sizes for projections on the replay copy: python -I sizes.py <root> <projection id>..."""
import json
import sys
from pathlib import Path
from typing import Any

from pring_cycle import reports
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths

paths = RuntimePaths.discover(Path(sys.argv[1]))
repository = ProjectionSetRepository(paths.database)
for projection_id in sys.argv[2:]:
    projection = repository.get(projection_id)
    bundle = reports.report_input_from_projection(projection)
    document = bundle.prompt_document()
    compact = json.dumps(
        {k: v for k, v in document.items() if k != "gap_list"},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    captured: dict[str, int] = {}

    def capture(name: str, prompt: str, *args: Any, **kwargs: Any) -> Any:
        captured["prompt"] = len(prompt.encode("utf-8"))
        raise RuntimeError("captured")

    original = reports.run_structured_cli
    reports.run_structured_cli = capture
    try:
        reports.CliReportAdapter("codex_cli").generate(bundle)
    except RuntimeError:
        pass
    finally:
        reports.run_structured_cli = original
    macro = (bundle.results or {}).get("macro_judgement")
    identifiers = sum(
        json.dumps(document).count(f'"{key}"')
        for key in ("claim_ids", "observation_version_ids", "selected_claim_id", "first_claim_ids")
    )
    print(json.dumps({
        "projection": projection_id,
        "target": projection.envelope.target_business_date,
        "model": projection.envelope.model_version_id,
        "contract": [bundle.schema_version, bundle.prompt_version],
        "report_input_compact_without_gap_list": len(compact.encode("utf-8")),
        "macro_results": len(json.dumps(macro, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) if macro else 0,
        "full_prompt": captured.get("prompt"),
        "identifier_keys_left": identifiers,
    }, ensure_ascii=False))
