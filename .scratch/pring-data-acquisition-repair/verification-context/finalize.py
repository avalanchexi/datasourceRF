"""Bind this replay-context change to terminal checks and exact workspace files."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-context/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', '6662bc2'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base


def read(path: Path) -> str:
    data = path.read_bytes()
    return data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig')


def log(name: str) -> str:
    return read(folder / f'verification-context-{name}')


associated = log('associated-01.txt')
match = re.search(r'(\d+) passed in ([0-9.]+)s', associated)
assert match is not None and int(match.group(1)) >= 400
assert not re.search(r'\d+ (failed|errors?)', associated)
for name, expected in (
    ('identity-red-01.txt', '1 failed'), ('scope-red-01.txt', '1 failed'),
    ('members-red-02.txt', '3 failed'), ('economic-red-01.txt', '1 failed'),
    ('warrant-red-01.txt', '1 failed'), ('failure-red-01.txt', '1 failed'),
    ('value-red-01.txt', '1 failed'), ('retired-red-01.txt', '1 failed'),
    ('retired-green-01.txt', '13 passed'), ('failure-green-01.txt', '5 passed'),
):
    assert expected in log(name), name
assert 'Success: no issues found in 92 source files' in log('mypy-final.txt')
assert 'All checks passed!' in log('ruff-final.txt')
assert '9 files already formatted' in log('format-final.txt')
fingerprint = json.loads(log('fingerprint.json'))
assert fingerprint['matched_source_files'] == 90
for item in fingerprint['files']:
    data = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(data).hexdigest() == item['lf_sha256'], item['path']

paths = [
    *(Path('src/pring_cycle') / f'{name}.py' for name in (
        'cli', 'model_evaluation', 'model_outputs', 'models', 'storage', 'context_replay_scope',
        'migrations/versions/0021_context_replay_outputs',
    )),
    Path('tests/models/test_candidate_replay.py'),
    Path('tests/models/test_candidate_admission.py'),
    folder / 'implementation-21-context-replay.md', folder / 'continuation-status.md',
    folder / 'normalized-consumption-boundary.md',
    folder / 'normalized-consumption-source-map.md',
    folder / 'issues/19-immutable-candidate-catalog.md', folder / 'issues/21-public-replay-120d.md',
    folder / 'verification-context/review.md', folder / 'verification-context/finalize.py',
    folder / 'verification-context-fingerprint.json',
    *sorted(folder.glob('verification-context-*.txt')),
]
files = []
for path in paths:
    data = path.read_bytes()
    assert data, path
    files.append({'path': path.as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
assert len(paths) == len(set(paths))
record = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'persisted daily PUBLIC context and visible source selection histories',
    'software_slice_passed': True, 'associated_tests': int(match.group(1)),
    'associated_duration_seconds': float(match.group(2)),
    'new_tests_in_associated_scope': 19,
    'mypy_source_files': 92, 'installed_python_sources': 90,
    'uv_lock_sha256': hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest(),
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'context_cli_api_persistence_verified': True,
    'lpr_same_value_vintage_invalidates_saved_replay': True,
    'older_warrant_vintage_changes_context_snapshot': True,
    'retired_invalid_warehouse_preserved_without_current_input_adoption': True,
    'old_0019_and_0020_runtime_migration_verified': True,
    'failed_context_input_and_reasons_preserved': True,
    'all_real_p1_p2_positive_consumption_verified': False,
    'new_catalog_active_worker_end_to_end_verified': False,
    'normalized_consumption_integrity_verified': False,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False, 'project_full_gate_passed': False,
    'production_cutover': False, 'new_network_requests': 0, 'real_qualified_ai_outputs': 0,
    'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
