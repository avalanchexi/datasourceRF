"""Create the combined checkpoint only after terminal, matching-code verification."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-connection/checkpoint.json'
base = '3e1b7d3f4f2421fa72ee2e30ffbaefb11da03f8d'
assert not destination.exists()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base


def read(path: Path) -> str:
    raw = path.read_bytes()
    return raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')


terminal = json.loads(read(folder / 'verification-connection/terminal.json'))
assert terminal['targeted']['exit_code'] == 0
assert terminal['full']['exit_code'] == 0
full_path = folder / terminal['full']['log']
assert full_path.name == 'verification-connection-full-01.txt'
full = read(full_path)
match = re.search(r'(\d+) passed in ([0-9.]+)s', full)
assert match and int(match.group(1)) == 1031
assert terminal['full']['state'] == 'completed'
assert terminal['full']['tests'] == int(match.group(1))
assert terminal['full']['duration_seconds'] == float(match.group(2))
assert not re.search(r'\d+ (failed|errors?|skipped|deselected)', full)
targeted = read(folder / terminal['targeted']['log'])
targeted_match = re.search(r'(\d+) passed in ([0-9.]+)s', targeted)
assert targeted_match and int(targeted_match.group(1)) == 257
assert terminal['targeted']['tests'] == int(targeted_match.group(1))
assert terminal['targeted']['duration_seconds'] == float(targeted_match.group(2))
assert not re.search(r'\d+ (failed|errors?|skipped|deselected)', targeted)
assert '92 source files' in read(folder / 'verification-connection-mypy-01.txt')
assert 'All checks passed!' in read(folder / 'verification-connection-ruff-final.txt')
assert '22 files already formatted' in read(folder / 'verification-connection-format-final.txt')

inputs = json.loads(read(folder / 'verification-connection-run-inputs.json'))
assert inputs['base_commit'] == base and len(inputs['files']) == 22
for item in inputs['files']:
    assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() == item['sha256']
fingerprint = json.loads(read(folder / 'verification-connection-fingerprint-final.json'))
assert fingerprint['matched_source_files'] == 90
assert len(fingerprint['files']) == 90
for item in fingerprint['files']:
    content = Path(item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(content).hexdigest() == item['lf_sha256'], item['path']

assert '6 failed, 1022 passed, 1 error' in read(folder / 'verification-normalized-full-01.txt')
for suffix in ('red-01', 'red-02', 'views-red-01', 'direct-red-01'):
    assert '1 failed' in read(folder / f'verification-connection-{suffix}.txt')
assert '3 passed' in read(folder / 'verification-connection-probe-01.txt')
for suffix in (
    'core-red-01', 'semantics-red-01', 'ingress-red-01', 'warrant-red-01',
    'warrant-time-red-01', 'warrant-definition-red-01', 'warrant-revision-red-02',
):
    assert '1 failed' in read(folder / f'verification-normalized-{suffix}.txt')
assert '10 passed' in read(folder / 'verification-normalized-warrant-revision-green-01.txt')

paths = [
    *(Path(item['path']) for item in inputs['files']),
    folder / 'continuation-status.md',
    folder / 'implementation-19-normalized-consumption.md',
    folder / 'implementation-database-connections.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'normalized-context-next-seams.md',
    folder / 'cny030-official-followup-20260909.md',
    *sorted((folder / 'verification-normalized').rglob('*.md')),
    folder / 'verification-normalized/finalize.py',
    *sorted((folder / 'verification-connection').rglob('*.md')),
    *sorted((folder / 'verification-connection').rglob('*.py')),
    folder / 'verification-connection/terminal.json',
    *sorted(folder.glob('verification-normalized-*.txt')),
    *sorted(folder.glob('verification-normalized-*.json')),
    *sorted(folder.glob('verification-connection-*.txt')),
    *sorted(folder.glob('verification-connection-*.json')),
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
    'scope': 'core/warrant normalized consumption and database connection lifetime',
    'software_slice_passed': True, 'default_suite_passed': True,
    'default_suite_tests': int(match.group(1)),
    'default_suite_duration_seconds': float(match.group(2)),
    'new_normalized_tests': 21, 'new_connection_tests': 2,
    'mypy_source_files': 92, 'installed_python_sources': 90,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'uv_lock_sha256': hashlib.sha256(Path('uv.lock').read_bytes()).hexdigest(),
    'core_normalized_consumer_integrity_verified': True,
    'warrant_normalized_consumer_integrity_verified': True,
    'database_connection_resource_regression_verified': True,
    'all_family_normalized_consumer_integrity_verified': False,
    'all_real_p1_p2_positive_consumption_verified': False,
    'new_catalog_active_worker_end_to_end_verified': False,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False, 'production_cutover': False,
    'real_qualified_ai_outputs': 0,
    'cny030_research': {'logical_searches': 4, 'web_tool_calls': 2,
                       'new_official_documents': 0, 'new_target_samples': 0},
    'project_full_gate_passed': False, 'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
