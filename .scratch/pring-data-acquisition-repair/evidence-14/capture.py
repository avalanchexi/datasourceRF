"""Bounded public GET receipts and read-only imports for research ticket 14."""
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CAS = Path('/home/tywin/.local/share/pring-cycle/artifacts/sha256')
ALLOWED = ('chinamoney.com.cn', 'pbc.gov.cn', 'stats.gov.cn', 'tushare.pro', 'treasury.gov', 'eia.gov', 'cboe.com', 'nasdaq.com', 'cmegroup.com', 'lbma.org.uk', 'ice.com', 'stlouisfed.org', 'fxcm.com')

def store(raw):
    digest = hashlib.sha256(raw).hexdigest()
    path = ROOT / digest
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    return {'sha256': digest, 'bytes': len(raw), 'local_file': path.name}

def append(name, record):
    path = ROOT / name
    rows = json.loads(path.read_text()) if path.exists() else []
    rows.append(record)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')

def get(url):
    host = urlsplit(url).hostname
    assert host and any(host == x or host.endswith('.'+x) for x in ALLOWED)
    record = {'url': url, 'method': 'GET', 'started_at': datetime.now(UTC).isoformat()}
    try:
        try:
            response = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'}), timeout=25)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(8_000_001)
            record.update(status=response.status, final_url=response.geturl(), headers={k:v for k,v in response.headers.items() if k.lower() in ('content-type','content-length','date','last-modified','etag')})
            record.update(store(raw))
            record['truncated'] = len(raw) > 8_000_000
    except Exception as error:
        record.update(error_type=type(error).__name__, error=str(error))
    record['received_at'] = datetime.now(UTC).isoformat()
    record['public_available_at'] = None
    append('receipts.json', record)
    print(json.dumps(record, ensure_ascii=False), flush=True)

def import_hash(digest):
    path = CAS / digest[:2] / digest
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    record = {'imported_at': datetime.now(UTC).isoformat(), 'origin_path': str(path), **store(raw)}
    append('imports.json', record)
    print(json.dumps(record), flush=True)

if __name__ == '__main__':
    if sys.argv[1] == 'get':
        for url in sys.argv[2:]:
            get(url)
    elif sys.argv[1] == 'import':
        for digest in sys.argv[2:]:
            import_hash(digest)
