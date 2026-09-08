"""Bind completed targeted retrieval checks without changing production state."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-warrants-targeted/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', '96964cf'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base

def read(path: Path) -> str:
    body = path.read_bytes()
    return body.decode('utf-16' if body.startswith(b'\xff\xfe') else 'utf-8-sig')

def log(name: str) -> str:
    return read(folder / f'verification-warrants-targeted-{name}')

assert '91 passed in 925.14s' in log('associated-01.txt')
assert '3 passed, 26 deselected in 4.58s' in log('final-01.txt')
assert 'Success: no issues found in 86 source files' in log('mypy-app.txt')
assert 'All checks passed!' in log('ruff-final.txt')
assert '2 files already formatted' in log('format-final.txt')
baseline = Counter(re.findall(r': error: (.+)', log('mypy-baseline.txt')))
current = Counter(re.findall(r': error: (.+)', log('mypy-03.txt')))
assert sum(baseline.values()) == 38 and baseline == current
fingerprint = json.loads(log('fingerprint.json'))
assert fingerprint['matched_source_files'] == 86
for item in fingerprint['files']:
    body = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(body).hexdigest() == item['lf_sha256'], item['path']

paths = [
    Path('src/pring_cycle/targeted_context.py'),
    Path('tests/integration/test_search_evidence.py'),
    folder / 'implementation-19-warrants-targeted.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'verification-warrants-targeted/review.md',
    folder / 'verification-warrants-targeted/finalize.py',
    *sorted(folder.glob('verification-warrants-targeted-*.txt')),
    folder / 'verification-warrants-targeted-fingerprint.json',
]
files = []
for path in paths:
    body = path.read_bytes()
    assert body, path
    files.append({'path': path.as_posix(), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
document = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'targeted eight-symbol warrant retrieval and physical-request lineage',
    'software_slice_passed': True, 'associated_tests': 91, 'final_focused_tests': 3,
    'application_mypy_files': 86, 'installed_sources': 86,
    'test_file_mypy_passed': False, 'test_file_mypy_baseline_errors': 38,
    'test_file_mypy_current_errors': 38, 'test_file_mypy_new_errors': 0,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'worker_120d_complete_member_density_verified': False,
    'real_source_certification': False, 'real_candidate_or_120d_replay': False,
    'project_full_gate_passed': False, 'production_cutover': False, 'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
