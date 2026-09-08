"""Bind this completed software slice without changing runtime or production state."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd()
folder = Path('.scratch/pring-data-acquisition-repair')
destination = folder / 'verification-warrants-members/checkpoint.json'
assert not destination.exists()

def git(*args: str) -> str:
    return subprocess.run(['git', *args], check=True, capture_output=True, encoding='utf-8').stdout.strip()

def read(relative: str | Path) -> str:
    content = (root / relative).read_bytes()
    return content.decode('utf-16' if content.startswith(b'\xff\xfe') else 'utf-8-sig')

base = git('rev-parse', 'b640610')
assert git('rev-parse', 'HEAD') == base
assert '238 passed in 459.45s' in read(folder / 'verification-warrants-members-associated-02.txt')
assert '12 passed, 141 deselected in 30.81s' in read(folder / 'verification-warrants-members-final-01.txt')
assert 'Success: no issues found in 87 source files' in read(folder / 'verification-warrants-members-mypy-final-02.txt')
assert 'All checks passed!' in read(folder / 'verification-warrants-members-ruff-final-02.txt')
assert '7 files already formatted' in read(folder / 'verification-warrants-members-format-final-02.txt')
fingerprint = json.loads(read(folder / 'verification-warrants-members-fingerprint.json'))
assert fingerprint['matched_source_files'] == 86
for item in fingerprint['files']:
    body = (root / item['path']).read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(body).hexdigest() == item['lf_sha256'], item['path']

paths = {
    'src/pring_cycle/context_projection.py', 'src/pring_cycle/evidence.py',
    'src/pring_cycle/model_evaluation.py', 'src/pring_cycle/search_evidence.py',
    'src/pring_cycle/tushare_context.py', 'src/pring_cycle/warrant_inputs.py',
    'tests/models/test_candidate_admission.py',
    str(folder / 'implementation-19-warrants-members.md').replace('\\', '/'),
    str(folder / 'issues/19-immutable-candidate-catalog.md').replace('\\', '/'),
    str(folder / 'issues/21-public-replay-120d.md').replace('\\', '/'),
    str(folder / 'verification-warrants-members/review.md').replace('\\', '/'),
    str(folder / 'verification-warrants-members/finalize.py').replace('\\', '/'),
}
for path in git('ls-files', '--others', '--exclude-standard', '--', folder.as_posix()).splitlines():
    if re.fullmatch(r'verification-warrants-[a-z0-9-]+\.(txt|json)', Path(path).name):
        paths.add(path)
files = []
for path in sorted(paths):
    body = (root / path).read_bytes()
    assert body, path
    files.append({'path': path, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
document = {
    'recorded_at': datetime.now(UTC).isoformat(), 'base_commit': base,
    'scope': 'warrant physical members, field lineage, and dual-as-of consumers',
    'software_slice_passed': True, 'associated_tests': 238, 'final_focused_tests': 12,
    'mypy_files': 87, 'installed_sources': 86,
    'spec_findings_remaining': 0, 'standards_findings_remaining': 0,
    'targeted_eight_symbol_router_complete': False,
    'worker_120d_complete_member_density_verified': False,
    'real_source_certification': False, 'real_candidate_or_120d_replay': False,
    'project_full_gate_passed': False, 'production_cutover': False, 'files': files,
}
with destination.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(document, stream, indent=2)
    stream.write('\n')
print(json.dumps({'checkpoint': destination.as_posix(), 'bound_files': len(files)}))
