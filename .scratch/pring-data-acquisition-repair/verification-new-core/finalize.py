"""Bind the registered-core acquisition slice without granting real model acceptance."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-new-core/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', '159a725'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base

def read(path: Path) -> str:
    body = path.read_bytes()
    return body.decode('utf-16' if body.startswith(b'\xff\xfe') else 'utf-8-sig')

def log(name: str) -> str:
    return read(folder / f'verification-new-core-{name}')

assert '252 passed in 504.38s' in log('associated-01.txt')
assert '17 passed, 168 deselected in 36.27s' in log('final-01.txt')
assert 'Success: no issues found in 87 source files' in log('mypy-final.txt')
assert 'All checks passed!' in log('ruff-final-02.txt')
assert '6 files already formatted' in log('format-final-02.txt')
fingerprint = json.loads(log('fingerprint-final.json'))
assert fingerprint['matched_source_files'] == 86
for item in fingerprint['files']:
    body = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(body).hexdigest() == item['lf_sha256'], item['path']

research = folder / 'core-replay-revision-boundary.md'
assert hashlib.sha256(research.read_bytes()).hexdigest() == (
    'd3ec241ac9a5b9a7c148d64151c27b652fcafc3aa9ac164218e25a20e6885622'
)
paths = [
    Path('src/pring_cycle/core_history.py'),
    Path('src/pring_cycle/evidence.py'),
    Path('src/pring_cycle/source_adapters.py'),
    Path('src/pring_cycle/source_contract_review.py'),
    Path('tests/models/test_candidate_admission.py'),
    Path('tests/integration/test_core_history_refresh.py'),
    folder / 'implementation-19-core-source.md',
    folder / 'issues/19-immutable-candidate-catalog.md',
    folder / 'verification-new-core/review.md',
    folder / 'verification-new-core/finalize.py',
    research,
    *sorted(folder.glob('verification-new-core-*.txt')),
    *sorted(folder.glob('verification-new-core-fingerprint*.json')),
]
files = []
for path in paths:
    body = path.read_bytes()
    assert body, path
    files.append({'path': path.as_posix(), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
document = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'registered-core acquisition, exact original admission, unknown PUBLIC preservation',
    'software_slice_passed': True, 'associated_tests': 252, 'final_targeted_tests': 17,
    'application_and_candidate_test_mypy_files': 87, 'installed_sources': 86,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False, 'real_qualified_ai_report': False,
    'project_full_gate_passed': False, 'production_cutover': False,
    'runtime_original_loss_or_corruption_tested': False,
    'historical_revision_replay_counterexample_executed': False,
    'replay_research_inputs_verified_before_local_rename': 8,
    'replay_research_links_verified': 24,
    'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
