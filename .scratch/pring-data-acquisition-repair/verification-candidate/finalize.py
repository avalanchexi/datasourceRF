"""Bind the candidate-output code slice to its actual checks and scoped files."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-candidate/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', '0c33710'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base


def read(path: Path) -> str:
    content = path.read_bytes()
    return content.decode('utf-16' if content.startswith(b'\xff\xfe') else 'utf-8-sig')


def log(name: str) -> str:
    return read(folder / f'verification-candidate-{name}')


associated = log('associated-01.txt')
match = re.search(r'(\d+) passed in ([0-9.]+)s', associated)
assert match is not None and int(match.group(1)) >= 300
assert not re.search(r'\d+ (failed|errors?)', associated)
assert '2 failed' in log('review-red-01.txt')
assert '2 passed' in log('review-green-01.txt')
assert '30 passed' in log('read-contract-green-01.txt')
assert '1 passed' in log('current-green-01.txt')
assert 'Success: no issues found in 89 source files' in log('mypy-final.txt')
assert 'All checks passed!' in log('ruff-final.txt')
assert '9 files already formatted' in log('format-final.txt')
fingerprint = json.loads(log('fingerprint.json'))
assert fingerprint['matched_source_files'] == 88
for item in fingerprint['files']:
    content = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(content).hexdigest() == item['lf_sha256'], item['path']

paths = [
    *(Path('src/pring_cycle') / f'{name}.py' for name in (
        'cli', 'domain/trend', 'model_evaluation', 'model_outputs', 'models', 'storage', 'web',
        'migrations/versions/0020_model_evaluation_outputs',
    )),
    Path('tests/models/test_candidate_replay.py'),
    folder / 'implementation-21-candidate-replay.md',
    folder / 'context-replay-snapshot-boundary.md',
    folder / 'continuation-status.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'issues/21-public-replay-120d.md',
    folder / 'verification-candidate/review.md',
    folder / 'verification-candidate/finalize.py',
    folder / 'verification-candidate-fingerprint.json',
    *sorted(folder.glob('verification-candidate-*.txt')),
]
files = []
for path in paths:
    content = path.read_bytes()
    assert content, path
    files.append({
        'path': path.as_posix(), 'bytes': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
    })
document = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'public candidate fields and durable core replay outputs',
    'software_slice_passed': True, 'associated_tests': int(match.group(1)),
    'associated_duration_seconds': float(match.group(2)),
    'new_candidate_tests_in_associated_scope': 34,
    'application_and_changed_test_mypy_files': 89, 'installed_python_sources': 88,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'core_candidate_cli_api_and_persistence_verified': True,
    'core_input_vintage_change_detected_with_identical_counts': True,
    'old_0019_runtime_migration_verified': True,
    'requested_range_failed_replay_preserved': True,
    'legacy_missing_candidate_counts_are_null': True,
    'new_catalog_active_worker_end_to_end_verified': False,
    'normalized_consumption_integrity_verified': False,
    'full_context_daily_output_snapshot_verified': False,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False,
    'project_full_gate_passed': False, 'production_cutover': False,
    'new_network_requests': 0, 'real_qualified_ai_outputs': 0,
    'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
