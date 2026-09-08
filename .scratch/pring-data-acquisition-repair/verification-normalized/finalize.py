"""Bind terminal verification to this batch's exact source and evidence files."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-normalized/checkpoint.json'
assert not destination.exists()
base = '3e1b7d3f4f2421fa72ee2e30ffbaefb11da03f8d'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base


def read(path: Path) -> str:
    raw = path.read_bytes()
    return raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')


full = read(folder / 'verification-normalized-full-01.txt')
match = re.search(r'(\d+) passed in ([0-9.]+)s', full)
assert match and int(match.group(1)) >= 1000
assert not re.search(r'\d+ (failed|errors?)', full)
assert '91 source files' in read(folder / 'verification-normalized-mypy-01.txt')
assert 'All checks passed!' in read(folder / 'verification-normalized-ruff-01.txt')
assert '8 files already formatted' in read(folder / 'verification-normalized-format-final.txt')
for suffix in (
    'core-red-01', 'semantics-red-01', 'ingress-red-01', 'warrant-red-01',
    'warrant-time-red-01', 'warrant-definition-red-01', 'warrant-revision-red-02',
):
    assert '1 failed' in read(folder / f'verification-normalized-{suffix}.txt')
assert '10 passed' in read(folder / 'verification-normalized-warrant-revision-green-01.txt')

inputs = json.loads(read(folder / 'verification-normalized-run-inputs.json'))
assert inputs['base_commit'] == base
for item in inputs['files']:
    assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() == item['sha256']
fingerprint = json.loads(read(folder / 'verification-normalized-fingerprint-final.json'))
assert fingerprint['matched_source_files'] == 90
for item in fingerprint['files']:
    content = Path(item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(content).hexdigest() == item['lf_sha256'], item['path']

paths = [
    *(Path(item['path']) for item in inputs['files']),
    folder / 'implementation-19-normalized-consumption.md',
    folder / 'continuation-status.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'normalized-context-next-seams.md',
    folder / 'verification-normalized/review.md',
    folder / 'verification-normalized/finalize.py',
    *sorted(folder.glob('verification-normalized-*.txt')),
    *sorted(folder.glob('verification-normalized-*.json')),
]
assert len(paths) == len(set(paths))
files = []
for path in paths:
    content = path.read_bytes()
    assert content, path
    files.append({'path': path.as_posix(), 'bytes': len(content),
                  'sha256': hashlib.sha256(content).hexdigest()})
record = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'registered core and warrant acquisition artifact consumption',
    'software_slice_passed': True, 'default_suite_passed': True,
    'default_suite_tests': int(match.group(1)),
    'default_suite_duration_seconds': float(match.group(2)),
    'new_tests': 21, 'mypy_source_files': 91, 'installed_python_sources': 90,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'uv_lock_sha256': hashlib.sha256(Path('uv.lock').read_bytes()).hexdigest(),
    'core_normalized_consumer_integrity_verified': True,
    'warrant_normalized_consumer_integrity_verified': True,
    'unknown_public_revision_preserved_in_system': True,
    'historical_target_public_boundary_preserved': True,
    'all_family_normalized_consumer_integrity_verified': False,
    'all_real_p1_p2_positive_consumption_verified': False,
    'new_catalog_active_worker_end_to_end_verified': False,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False,
    'production_cutover': False, 'new_network_requests': 0,
    'real_qualified_ai_outputs': 0, 'project_full_gate_passed': False,
    'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
