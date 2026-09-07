"""At most four explicit anonymous official original-notice GETs, with no automatic redirects."""
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def get(url):
    parsed = urlsplit(url)
    assert parsed.scheme == "https" and (parsed.hostname == "pbc.gov.cn" or parsed.hostname.endswith(".pbc.gov.cn") or parsed.hostname in {'jr.jl.gov.cn', 'www.csrc.gov.cn', 'www.gov.cn', 'www.scio.gov.cn'})
    path = ROOT / "receipts.json"
    receipts = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    assert len(receipts) < 4, "Four GET budget exhausted"
    assert url not in {r["url"] for r in receipts}, "Do not retry an existing URL"
    record = {"method": "GET", "url": url, "started_at": datetime.now(UTC).isoformat(), "automatic_redirects": False}
    try:
        try:
            response = build_opener(NoRedirect()).open(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"}), timeout=15)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(8_000_001)
            sha = hashlib.sha256(raw).hexdigest()
            artifact = ROOT / sha
            if artifact.exists():
                assert artifact.read_bytes() == raw
            else:
                artifact.write_bytes(raw)
            record.update(status=response.status, final_url=response.geturl(), headers={k: v for k, v in response.headers.items() if k.lower() in ("date", "content-type", "content-length", "last-modified", "etag", "location")}, bytes=len(raw), sha256=sha, local_file=sha, truncated=len(raw) > 8_000_000)
    except Exception as error:
        record.update(error_type=type(error).__name__, error=str(error))
    record.update(received_at=datetime.now(UTC).isoformat(), public_available_at=None)
    receipts.append(record)
    path.write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    assert len(sys.argv) == 2
    get(sys.argv[1])
