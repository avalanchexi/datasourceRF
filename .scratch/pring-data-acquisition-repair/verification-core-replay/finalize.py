"""Bind the PUBLIC replay software checks and separate connectivity research."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-core-replay/checkpoint.json'
assert not destination.exists()
base = subprocess.check_output(['git', 'rev-parse', '4084834'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == base

def read(path: Path) -> str:
    body = path.read_bytes()
    return body.decode('utf-16' if body.startswith(b'\xff\xfe') else 'utf-8-sig')

def log(name: str) -> str:
    return read(folder / f'verification-core-replay-{name}')

assert '269 passed in 422.36s' in log('associated-01.txt')
assert '23 passed in 62.94s' in log('final-01.txt')
assert 'Success: no issues found in 88 source files' in log('mypy-final.txt')
assert 'All checks passed!' in log('ruff-final.txt')
assert '3 files already formatted' in log('format-final.txt')
match = re.search(r'(\{"evaluated_days"[^\r\n]+\})', log('final-01.txt'))
assert match is not None
benchmark = json.loads(match.group(1))
assert benchmark['input_days'] == 2338 and benchmark['evaluated_days'] == 1995
assert benchmark['source_claims'] == 7015 and benchmark['historical_revisions'] == 1
assert benchmark['evaluation_seconds'] < 900
assert not benchmark['real_china_calendar_or_full_parallel_replay_acceptance']
assert benchmark['evidence_hash'] == 'b1c5bd496ccbb9a6b820116448ff7691286c5057ba74fef2f30b7b4920589fd1'
fingerprint = json.loads(log('fingerprint.json'))
assert fingerprint['matched_source_files'] == 86
for item in fingerprint['files']:
    body = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(body).hexdigest() == item['lf_sha256'], item['path']
research = folder / 'core-original-consumption-boundary.md'
assert hashlib.sha256(research.read_bytes()).hexdigest() == (
    'd27e012154b123c973568fbbb22a7f6c53d2bdc1da3eda1d845c5e085eb3b167'
)
network = folder / 'evidence-18-connectivity-20260909'
for name in ('wsl-direct.txt', 'windows-proxy.txt'):
    assert 'status=000' in read(network / name)
    assert '(28)' in read(network / name)
listener = json.loads(read(network / 'listener.json'))
assert listener['LocalAddress'] == '127.0.0.1' and listener['LocalPort'] == 10809

paths = [
    Path('src/pring_cycle/model_evaluation.py'),
    Path('tests/models/test_model_evaluation_regressions.py'),
    folder / 'verification-core-replay/benchmark.py',
    folder / 'verification-core-replay/review.md',
    folder / 'verification-core-replay/finalize.py',
    folder / 'implementation-21-core-public-replay.md',
    folder / 'issues/21-public-replay-120d.md',
    folder / 'issues/18-report-cli-evidence.md',
    research,
    *sorted(network.iterdir()),
    *sorted(folder.glob('verification-core-replay-*.txt')),
    folder / 'verification-core-replay-fingerprint.json',
]
files = []
for path in paths:
    body = path.read_bytes()
    assert body, path
    files.append({'path': path.as_posix(), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
document = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'per-cutoff PUBLIC core revision selection and input path fingerprint',
    'software_slice_passed': True, 'associated_tests': 269, 'final_tests': 23,
    'application_and_changed_test_mypy_files': 88, 'installed_python_sources': 86,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'synthetic_benchmark': benchmark,
    'real_source_certification': False, 'real_complete_candidate': False,
    'real_120_china_trading_day_replay': False, 'candidate_fields_replay_acceptance': False,
    'project_full_gate_passed': False, 'production_cutover': False,
    'runtime_core_original_loss_or_corruption_tested': False,
    'core_original_research_inputs_verified_before_final_type_annotations': 16,
    'core_original_research_links_verified': 27,
    'network_model_requests': 0, 'real_qualified_ai_outputs': 0,
    'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
