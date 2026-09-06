"""Replay an existing official raw document into an isolated candidate context."""
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import certified_model_v0001_manifest
from pring_cycle.official_context import ingest_official_context_document
from pring_cycle.runtime import RuntimePaths, initialize_runtime

folder = Path(__file__).resolve().parent
digest = "1ae383d1e5934bdb3484933c7e359f9ac4b04850d2952be08c627897bf37a7f5"
url = "https://www.stats.gov.cn/sj/zxfbhjd/202608/t20260809_1965008.html"
content = (folder / "nbs-cpi-202607.html").read_bytes()
assert hashlib.sha256(content).hexdigest() == digest
paths = RuntimePaths.discover(Path("/home/tywin/.cache/pring-cycle/verification") / ("repair-03-sample-" + uuid4().hex))
initialize_runtime(paths)
before_import = datetime.now(UTC)
result = ingest_official_context_document(
    paths, content, family="nbs_core_cpi", source_url=url, expected_period="2026-07",
    fetched_at=before_import, definition_version="metric-catalog-v0001",
)
now = datetime.now(UTC)
repository = EvidenceRepository(paths.database)
receipts = AcquisitionRepository(paths.database, paths.artifacts)
expected = {
    "CN_CORE_CPI": {"mom": 0.3, "yoy": 0.9, "cumulative_average_yoy": 1.1},
    "CN_CPI_HEADLINE": {"mom": -0.1, "yoy": 0.5, "cumulative_average_yoy": 0.9},
}
observed = {}
for observation_id in result.observation_ids:
    trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=now)
    measure = trace.dimensions["measure"]
    expected_value = expected[trace.metric_id][measure]
    observed.setdefault(trace.metric_id, {})[measure] = trace.selected_value
    assert trace.selected_value == expected_value
    assert trace.acquisition_status == "linked"
    receipt = trace.acquisitions[0]
    assert receipt.api_name == "document_import"
    assert receipts.read_content(receipt.acquisition_id, "raw") == content
    assert trace.claims[0].public_available_at == datetime(2026, 8, 9, 1, 30, tzinfo=UTC)
    assert repository.query(observation_id, mode=AsOfMode.SYSTEM, as_of=before_import).selected_value is None
    assert repository.query(observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 9, 1, 29, tzinfo=UTC)).selected_value is None
    assert repository.query(observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 9, 1, 30, tzinfo=UTC)).selected_value == expected_value
projection = build_context_projection(
    repository, as_of=now, model_manifest=certified_model_v0001_manifest(),
    target_business_date="2026-08-28", persist_derived=False,
)
document = asdict(projection)
serialized = json.dumps(document, ensure_ascii=False, default=str)
assert "CN_CORE_CPI" in serialized
assert "awaiting_source_certification" in serialized
output = {
    "status": "passed", "sample_source": url, "raw_sha256": digest, "raw_byte_count": len(content),
    "original_acquisition": "existing registered CAS; original receive time not independently established",
    "this_acquisition": "document_import at current system time; not a fresh HTTP fetch",
    "publication": "official page labelled 2026/08/09 09:30; UTC+08:00",
    "independent_expected_values_from_table": expected, "observed": observed,
    "runtime": paths.as_document(), "result": asdict(result),
    "claims_linked": len(result.claim_ids), "new_source_certifications": 0,
    "production_writes": 0, "network_requests": 0,
    "context_projection": document,
}
(folder / "official-sample-result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps({key: output[key] for key in ("status", "raw_sha256", "observed", "claims_linked", "new_source_certifications")}, ensure_ascii=False))
