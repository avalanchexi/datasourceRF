"""Bind the completed warrant-history software slice and separate research outputs."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-warrants-history/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', 'b8cf9b3'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base

def read(path: Path) -> str:
    body = path.read_bytes()
    return body.decode('utf-16' if body.startswith(b'\xff\xfe') else 'utf-8-sig')

def log(name: str) -> str:
    return read(folder / f'verification-warrants-history-{name}')

assert '219 passed in 471.53s' in log('associated-01.txt')
assert '2 passed, 153 deselected in 42.45s' in log('green-01.txt')
assert 'Success: no issues found in 87 source files' in log('mypy-final.txt')
assert 'All checks passed!' in log('ruff-final.txt')
assert '4 files already formatted' in log('format-final.txt')
fingerprint = json.loads(log('fingerprint.json'))
assert fingerprint['matched_source_files'] == 86
for item in fingerprint['files']:
    body = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(body).hexdigest() == item['lf_sha256'], item['path']

paths = [
    Path('src/pring_cycle/warrant_inputs.py'),
    Path('src/pring_cycle/context_projection.py'),
    Path('src/pring_cycle/worker.py'),
    Path('tests/models/test_candidate_admission.py'),
    folder / 'implementation-19-warrants-history.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'issues/21-public-replay-120d.md',
    folder / 'verification-warrants-history/review.md',
    folder / 'verification-warrants-history/finalize.py',
    folder / 'verification-warrants-history/research-verification.json',
    folder / 'cny030-official-followup-20260908.md',
    folder / 'new-catalog-core-consumption-boundary.md',
    *sorted(folder.glob('verification-warrants-history-*.txt')),
    folder / 'verification-warrants-history-fingerprint.json',
]
files = []
for path in paths:
    body = path.read_bytes()
    assert body, path
    files.append({'path': path.as_posix(), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
document = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'verified per-symbol warrant history coverage for registered catalog Worker',
    'software_slice_passed': True, 'associated_tests': 219,
    'application_and_changed_test_mypy_files': 87, 'installed_sources': 86,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'worker_120d_complete_member_density_software_passed': True,
    'real_new_catalog_worker_publication_tested': False,
    'real_source_certification': False, 'real_candidate_or_120d_replay': False,
    'project_full_gate_passed': False, 'production_cutover': False,
    'new_cny030_official_numeric_samples': 0,
    'new_core_catalog_consumption_implemented': False, 'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
