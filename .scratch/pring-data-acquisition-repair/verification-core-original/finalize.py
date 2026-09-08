"""Bind the core-original consumer software slice, without claiming real acceptance."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-core-original/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', 'dd744ff'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base

def read(path: Path) -> str:
    content = path.read_bytes()
    return content.decode('utf-16' if content.startswith(b'\xff\xfe') else 'utf-8-sig')

def log(name: str) -> str:
    return read(folder / f'verification-core-original-{name}')

associated = log('associated-02.txt')
match = re.search(r'(\d+) passed in ([0-9.]+)s', associated)
assert match is not None and int(match.group(1)) >= 300
assert not re.search(r'\d+ (failed|errors?)', associated)
assert '8 passed' in log('green-04.txt')
assert '2 failed' in log('red-01.txt')
assert 'DID NOT RAISE' in log('replay-red-02.txt')
assert 'assert {149} == {1}' in log('reads-red-01.txt')
assert 'Success: no issues found in 87 source files' in log('mypy-final.txt')
assert 'All checks passed!' in log('ruff-final.txt')
assert '6 files already formatted' in log('format-final.txt')
fingerprint = json.loads(log('fingerprint.json'))
assert fingerprint['matched_source_files'] == 86
for item in fingerprint['files']:
    content = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(content).hexdigest() == item['lf_sha256'], item['path']
research_check = json.loads(read(folder / 'verification-core-original/research-input-check.json'))
assert research_check['verified_inputs_before_issue_comment'] == 14
assert research_check['verified_links'] == 38
assert hashlib.sha256((root / research_check['research_path']).read_bytes()).hexdigest() == (
    research_check['sha256']
)

paths = [
    *(Path('src/pring_cycle') / f'{name}.py' for name in (
        'evidence', 'source_adapters', 'search_evidence', 'model_evaluation', 'worker'
    )),
    Path('tests/models/test_candidate_admission.py'),
    folder / 'implementation-19-core-original-consumption.md',
    folder / 'continuation-status.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'issues/21-public-replay-120d.md',
    folder / 'verification-core-original/review.md',
    folder / 'verification-core-original/finalize.py',
    folder / 'verification-core-original/research-input-check.json',
    folder / 'core-candidate-replay-boundary.md',
    folder / 'verification-core-original-fingerprint.json',
    *sorted(folder.glob('verification-core-original-*.txt')),
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
    'scope': 'registered core raw originals at consumption',
    'software_slice_passed': True, 'associated_tests': int(match.group(1)),
    'associated_duration_seconds': float(match.group(2)),
    'targeted_tests_before_test_type_annotations': 8,
    'application_and_changed_test_mypy_files': 87, 'installed_python_sources': 86,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'new_catalog_system_selector_and_public_history_verified': True,
    'original_reads_per_receipt_per_evaluation': 1,
    'synthetic_public_input_days': 168, 'synthetic_base_claims': 504,
    'new_catalog_active_worker_end_to_end_verified': False,
    'normalized_consumption_integrity_verified': False,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False, 'candidate_fields_replay_acceptance': False,
    'project_full_gate_passed': False, 'production_cutover': False,
    'new_network_requests': 0, 'real_qualified_ai_outputs': 0,
    'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
