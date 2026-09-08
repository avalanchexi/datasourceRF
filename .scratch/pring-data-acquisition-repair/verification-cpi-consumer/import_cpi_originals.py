"""One-time CPI document imports and one bounded NBS terms GET; no certification."""
import argparse
import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.official_context import parse_official_context_document
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--execute", action="store_true", required=True)
parser.parse_args()
root = Path.cwd().resolve()
assert root == Path("/mnt/d/cursor/datasourceRF")
repair = root / ".scratch/pring-data-acquisition-repair"
report = repair / "cpi-certification-next-boundary.md"
assert hashlib.sha256(report.read_bytes()).hexdigest() == "b1716e9ba69a6e8041334bed17c7595d10bfc9fa88efbffba503f06cc9f12319"
inputs = re.findall(
    r"^\| \[(\d{4}-\d{2})\]\((https://[^)]+)\).*?\[R\d+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})`",
    report.read_text(encoding="utf-8"), re.M,
)
assert len(inputs) == 8
audit = repair / "p1-cpi-full-value-audit.md"
assert hashlib.sha256(audit.read_bytes()).hexdigest() == "1f57b4ee4670e928364225944f685823ef30817a7968a42194892489d1c8c751"
rows = re.findall(
    r"^\| \d+ \| R\d+ / (\d{4}-\d{2}) \| (总体|核心) \| (mom|yoy|累计) \| [^|]+ \| (-?[\d.]+) \|",
    audit.read_text(encoding="utf-8"), re.M,
)
assert len(rows) == 46
expected = {(period, "headline" if category == "总体" else "ex_food_energy",
             "cumulative_average_yoy" if measure == "累计" else measure): float(value)
            for period, category, measure, value in rows}
runtime = Path("/home/tywin/.cache/pring-cycle/verification/cpi-document-import-20260908")
output = repair / "evidence-cpi-import-20260908"
assert not runtime.exists() and not output.exists(), "one_time_import_already_started"
paths = RuntimePaths.discover(runtime)
initialize_runtime(paths)
output.mkdir()
repository = AcquisitionRepository(paths.database, paths.artifacts)
document = {
    "status": "running", "runtime": str(runtime), "database": str(paths.database),
    "started_at": datetime.now(UTC).isoformat(), "execution_fingerprint": execution_fingerprint(paths),
    "source_claims_created": 0, "source_certification_grants": 0, "production_writes": 0,
    "historical_system_availability_restored": False, "real_candidate_models_created": 0,
    "network_attempts": 0, "receipts": [],
}


def record(acquired, normalized):
    receipt = repository.get(acquired.receipt.acquisition_id)
    assert receipt.state == "validated"
    for digest in (receipt.raw_hash, receipt.normalized_hash):
        assert digest is not None
        content = (paths.artifacts / digest[:2] / digest).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        with (output / digest).open("xb") as stream:
            stream.write(content)
    document["receipts"].append({"receipt": asdict(receipt), "normalized_unreviewed": normalized})


try:
    scalar_count = 0
    for period, url, target, size, digest in inputs:
        name = target.partition("#")[0]
        prefix = "//wsl.localhost/Ubuntu-22.04"
        source = Path(name[len(prefix):]) if name.startswith(prefix) else repair / name
        content = source.read_bytes()
        assert (len(content), hashlib.sha256(content).hexdigest()) == (int(size), digest)

        def parse(raw):
            parsed = parse_official_context_document(
                raw, family="nbs_core_cpi", source_url=url, expected_period=period,
                fetched_at=datetime.now(UTC),
            )
            values = {(period, item.dimensions["category"], item.dimensions["measure"]): item.value
                      for item in parsed.scalars}
            assert values == {key: value for key, value in expected.items() if key[0] == period}
            return parsed

        acquired = repository.capture(
            provider="国家统计局", api_name="document_import",
            parameters={"source_url": url, "period": period, "imported_from": str(source)},
            fields="headline,ex_food_energy:mom,yoy,cumulative_average_yoy",
            parser_version="official-context-parser-v0004", fetch=source.read_bytes,
            parse=parse, normalize=asdict,
        )
        record(acquired, asdict(acquired.value))
        scalar_count += len(acquired.value.scalars)
    assert scalar_count == 46
    document["literal_values_verified"] = scalar_count
    terms_url = "https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html"
    response_metadata = {}

    def fetch_terms():
        document["network_attempts"] += 1
        with open_no_redirects(Request(terms_url, headers={"User-Agent": "pring-cycle/source-review"}), timeout=15) as response:
            response_metadata.update(status=response.status, final_url=response.geturl(),
                                     media_type=response.headers.get_content_type())
            return response.read(300001)

    def parse_terms(raw):
        assert response_metadata == {"status": 200, "final_url": terms_url, "media_type": "text/html"}
        assert 0 < len(raw) <= 300000
        text = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", raw.decode("utf-8")))
        assert "下载和使用" in text and "统计数据" in text and "数据使用" in text
        return {"source_url": terms_url, "http": response_metadata,
                "finding": "NBS statistical data download/use terms captured for formal review",
                "review_status": "raw_preparation_not_certification"}

    acquired = repository.capture(
        provider="国家统计局", api_name="official_http_get",
        parameters={"source_url": terms_url}, fields="data_use_terms",
        parser_version="nbs-terms-evidence-check-v0001", fetch=fetch_terms,
        parse=parse_terms, normalize=lambda value: value, max_error_body_bytes=300001,
    )
    record(acquired, acquired.value)
    document["status"] = "completed_acquisition_preparation"
except Exception as error:
    document["status"] = "incomplete_acquisition_preparation"
    document["error_type"] = type(error).__name__
    raise
finally:
    document["completed_at"] = datetime.now(UTC).isoformat()
    (output / "receipts.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8",
    )
    print(json.dumps({"status": document["status"], "validated_receipts": len(document["receipts"]),
                      "literal_values": document.get("literal_values_verified", 0),
                      "network_attempts": document["network_attempts"], "source_claims": 0}))
