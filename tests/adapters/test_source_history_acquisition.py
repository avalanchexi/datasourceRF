import json
from datetime import UTC, datetime
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request
from urllib.response import addinfourl

import pytest

from pring_cycle.acquisition import (
    AcquisitionRepository,
    acquisition_analysis_context,
    own_acquisitions,
)
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_history import smoke_source_history


def test_history_discovery_http_error_retains_failed_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requests: list[str] = []
    body = b"<html>official listing unavailable</html>"

    def unavailable(request: Request, *, timeout: int) -> None:
        requests.append(request.full_url)
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(body))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", unavailable)
    started = datetime.now(UTC)
    with pytest.raises(HTTPError):
        smoke_source_history(paths, target_business_date="2026-08-28")
    completed = datetime.now(UTC)
    assert requests == ["https://www.pbc.gov.cn/diaochatongjisi/116219/116225/11871-1.html"]
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = repository.history()
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.state == "failed" and receipt.error_type == "HTTPError"
    assert receipt.received_at is not None
    assert started <= receipt.started_at <= receipt.received_at <= completed
    assert receipt.validated_at is None
    assert repository.read_content(receipt.acquisition_id, "raw") == body
    assert receipt.parameters["source_url"] == requests[0]
    assert receipt.parameters["target_business_date"] == "2026-08-28"


class Reply(BytesIO):
    def __init__(self, url: str, content: bytes, status: int = 200) -> None:
        super().__init__(content)
        self.url = url
        self.status = status
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def geturl(self) -> str:
        return self.url


class RedirectReply(addinfourl):
    msg: str


def test_history_threaded_fetch_errors_retain_response_and_run_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="history-transport-fixture",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    requests: list[str] = []
    body = b"<html>history document unavailable</html>"

    def transport(request: Request, *, timeout: int) -> Reply:
        requests.append(request.full_url)
        if request.full_url.rsplit("/", 1)[-1].startswith(("11871-", "17081-")):
            return Reply(request.full_url, b"<html><body>No links</body></html>")
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(body))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", transport)
    with (
        own_acquisitions(paths.database, run.run_id, "source_history"),
        pytest.raises(HTTPError),
    ):
        smoke_source_history(paths, target_business_date="2026-08-28")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = repository.history()
    assert len(receipts) == len(requests)
    listings = [receipt for receipt in receipts if receipt.api_name == "history_listing"]
    documents = [receipt for receipt in receipts if receipt.api_name == "history_document"]
    assert len(listings) == 14
    assert len(documents) == 8
    assert all(receipt.state == "validated" for receipt in listings)
    for receipt in documents:
        assert receipt.state == "failed" and receipt.error_type == "HTTPError"
        assert receipt.received_at is not None and receipt.validated_at is None
        assert repository.read_content(receipt.acquisition_id, "raw") == body
        assert acquisition_analysis_context(paths.database, (receipt.acquisition_id,)) == {
            "run_id": run.run_id,
            "target_business_date": "2026-08-28",
        }


@pytest.mark.parametrize("failure", ["redirect", "status", "oversize"])
def test_invalid_history_listing_keeps_received_body_unvalidated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    body = b"x" * 1_000_001 if failure == "oversize" else b"<html>listing</html>"
    calls: list[str] = []

    def transport(request: Request, *, timeout: int) -> Reply:
        calls.append(request.full_url)
        if len(calls) > 1:
            raise RuntimeError("invalid listing was accepted")
        return Reply(
            request.full_url + "?redirected" if failure == "redirect" else request.full_url,
            body,
            503 if failure == "status" else 200,
        )

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    with pytest.raises(ValueError, match="source_history_listing_"):
        smoke_source_history(paths, target_business_date="2026-08-28")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = repository.history()
    assert receipt.state == "failed"
    assert receipt.received_at is not None and receipt.validated_at is None
    assert repository.read_content(receipt.acquisition_id, "raw") == body


def test_valid_listing_has_distinct_receipt_before_next_request_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    body = b'<html><a href="/about">About the bank</a></html>'
    calls: list[str] = []

    def transport(request: Request, *, timeout: int) -> Reply:
        calls.append(request.full_url)
        if len(calls) == 1:
            return Reply(request.full_url, body)
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(b"failed"))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    before = datetime.now(UTC)
    with pytest.raises(HTTPError):
        smoke_source_history(paths, target_business_date="2026-08-28")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    valid, failed = repository.history()
    assert len(calls) == 2
    assert valid.state == "validated" and failed.state == "failed"
    assert valid.received_at is not None and valid.validated_at is not None
    assert before <= valid.started_at <= valid.received_at <= valid.validated_at
    assert valid.validated_at <= failed.started_at
    assert repository.read_content(valid.acquisition_id, "raw") == body
    assert b"Aboutthebank" in repository.read_content(valid.acquisition_id, "normalized")


@pytest.mark.parametrize("failure", ["redirect", "status", "invalid_document"])
def test_history_document_validation_failure_retains_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    body = b"<html>document without the requested reporting period</html>"

    def transport(request: Request, *, timeout: int) -> Reply:
        if request.full_url.rsplit("/", 1)[-1].startswith(("11871-", "17081-")):
            return Reply(request.full_url, b"<html>No links</html>")
        return Reply(
            request.full_url + "?redirected" if failure == "redirect" else request.full_url,
            body,
            503 if failure == "status" else 200,
        )

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", transport)
    with pytest.raises(ValueError):
        smoke_source_history(paths, target_business_date="2026-08-28")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    documents = [r for r in repository.history() if r.api_name == "history_document"]
    assert len(documents) == 8
    for receipt in documents:
        assert receipt.state == "failed" and receipt.error_type == "ValueError"
        assert receipt.received_at is not None and receipt.validated_at is None
        assert repository.read_content(receipt.acquisition_id, "raw") == body


def test_valid_audited_history_document_finishes_validation_when_peer_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    fixture = Path(__file__).resolve().parents[1] / "fixtures/pbc_social_financing_202501.html"
    body = fixture.read_bytes()
    url = "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554511660/index.html"

    def transport(request: Request, *, timeout: int) -> Reply:
        if request.full_url.rsplit("/", 1)[-1].startswith(("11871-", "17081-")):
            return Reply(request.full_url, b"<html>No links</html>")
        if request.full_url == url:
            return Reply(url, body)
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(b"failed"))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", transport)
    before = datetime.now(UTC)
    with pytest.raises(HTTPError):
        smoke_source_history(paths, target_business_date="2026-08-28")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = [r for r in repository.history() if r.parameters["source_url"] == url]
    assert receipt.state == "validated"
    assert receipt.received_at is not None and receipt.validated_at is not None
    assert before <= receipt.started_at <= receipt.received_at <= receipt.validated_at
    assert repository.read_content(receipt.acquisition_id, "raw") == body
    normalized = json.loads(repository.read_content(receipt.acquisition_id, "normalized"))
    assert normalized["metric_ids"] == ["CN_SF_COMPONENTS", "CN_SF_TOTAL"]
    assert normalized["period"] == "2025-01"
    assert normalized["artifact_hash"] == receipt.raw_hash
    assert normalized["source_url"] == url


def test_history_redirect_does_not_make_a_second_physical_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    calls: list[str] = []

    def https_response(handler: object, request: Request) -> addinfourl:
        calls.append(request.full_url)
        headers = Message()
        headers["Location"] = "https://www.pbc.gov.cn/redirected"
        status = 302 if len(calls) == 1 else 200
        response = RedirectReply(
            BytesIO(b"original redirect body"), headers, request.full_url, status
        )
        response.msg = "Found" if status == 302 else "OK"
        return response

    monkeypatch.setattr("urllib.request.HTTPSHandler.https_open", https_response)
    with pytest.raises((HTTPError, ValueError)):
        smoke_source_history(paths, target_business_date="2026-08-28")
    assert calls == ["https://www.pbc.gov.cn/diaochatongjisi/116219/116225/11871-1.html"]
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = repository.history()
    assert receipt.state == "failed" and receipt.error_type == "HTTPError"
    assert repository.read_content(receipt.acquisition_id, "raw") == b"original redirect body"


def test_history_http_error_body_retention_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    body = b"x" * 1_000_011

    def unavailable(request: Request, *, timeout: int) -> None:
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(body))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", unavailable)
    with pytest.raises(HTTPError):
        smoke_source_history(paths, target_business_date="2026-08-28")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = repository.history()
    assert repository.read_content(receipt.acquisition_id, "raw") == body[:1_000_001]
    assert receipt.parameters["response_read_limit_bytes"] == "1000001"
    assert receipt.state == "failed" and receipt.validated_at is None


@pytest.mark.parametrize("wrapper", ["invalid_wrapper", "valid_wrapper_invalid_html"])
def test_history_browser_import_preserves_wrapper_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrapper: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    captures = tmp_path / "captures"
    captures.mkdir()
    raw = (
        b"invalid capture wrapper"
        if wrapper == "invalid_wrapper"
        else b'### Result\r\n"<html>invalid reporting period</html>"\r\n### Ran Playwright code'
    )
    (captures / "nbs_gdp--2023-Q4.eval.txt").write_bytes(raw)

    def transport(request: Request, *, timeout: int) -> Reply:
        if request.full_url.rsplit("/", 1)[-1].startswith(("11871-", "17081-")):
            return Reply(request.full_url, b"<html>No links</html>")
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(b"failed"))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", transport)
    with pytest.raises((HTTPError, ValueError, FileNotFoundError)):
        smoke_source_history(
            paths, target_business_date="2026-08-28", browser_capture_root=captures
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = [
        r
        for r in repository.history()
        if r.parameters.get("families") == "nbs_gdp" and r.parameters.get("period") == "2023-Q4"
    ]
    assert receipt.state == "failed" and receipt.validated_at is None
    assert receipt.received_at is not None
    assert repository.read_content(receipt.acquisition_id, "raw") == raw
    assert receipt.parameters["transport"] == "browser_capture_import"
    assert receipt.parameters["target_business_date"] == "2026-08-28"


def test_valid_history_browser_wrapper_links_original_to_decoded_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    captures = tmp_path / "captures"
    captures.mkdir()
    fixture = Path(__file__).resolve().parents[1] / "fixtures/nbs_gdp_2023q4.html"
    html = fixture.read_bytes()
    raw = (
        "### Result\r\n"
        + json.dumps(html.decode("utf-8"), ensure_ascii=False)
        + "\r\n### Ran Playwright code"
    ).encode("utf-8")
    (captures / "nbs_gdp--2023-Q4.eval.txt").write_bytes(raw)

    def transport(request: Request, *, timeout: int) -> Reply:
        if request.full_url.rsplit("/", 1)[-1].startswith(("11871-", "17081-")):
            return Reply(request.full_url, b"<html>No links</html>")
        raise HTTPError(request.full_url, 503, "unavailable", Message(), BytesIO(b"failed"))

    monkeypatch.setattr("pring_cycle.source_history.urlopen", transport)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", transport)
    with pytest.raises((HTTPError, FileNotFoundError)):
        smoke_source_history(
            paths, target_business_date="2026-08-28", browser_capture_root=captures
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = [
        r
        for r in repository.history()
        if r.parameters.get("families") == "nbs_gdp" and r.parameters.get("period") == "2023-Q4"
    ]
    assert receipt.state == "validated" and receipt.validated_at is not None
    assert repository.read_content(receipt.acquisition_id, "raw") == raw
    normalized = json.loads(repository.read_content(receipt.acquisition_id, "normalized"))
    html_sha = "7f583c54493030fb019cbd09de3c0a4323691125b3d72fc8627ab5425d2b6861"
    assert normalized["artifact_hash"] == html_sha and receipt.raw_hash != html_sha
    assert (paths.artifacts / html_sha[:2] / html_sha).read_bytes() == html
    assert normalized["metric_ids"] == ["CN_GDP"]
    assert normalized["period"] == "2023-Q4"
    assert receipt.parameters["transport"] == "browser_capture_import"
