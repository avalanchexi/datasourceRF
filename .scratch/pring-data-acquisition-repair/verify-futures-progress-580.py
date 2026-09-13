"""Verify a bounded ticket 11 progress checkpoint, never whole-ticket acceptance."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
assert Path.cwd() == ROOT
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert head == '5e186f740be3d275cba5664a13ef0290e6a57916'
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).strip()
names = ['review-fixes-green-580', 'types-580', 'lint-580', 'format-580']
receipts = []
frozen = None
environment = None
for name in names:
    path = BASE / f'verification-futures-{name}.json'
    raw = path.read_bytes()
    record = json.loads(raw)
    assert record['status'] == 'passed' and record['test_exit_code'] == 0
    assert record['helper_inputs_unchanged'] and record['before'] == record['after']
    if frozen is None:
        frozen = record['frozen_inputs']
        environment = record['after']
    else:
        assert record['frozen_inputs'] == frozen
        assert record['after'] == environment
    log = (BASE / record['log']['path']).read_bytes()
    assert len(log) == record['log']['bytes']
    assert hashlib.sha256(log).hexdigest() == record['log']['sha256']
    receipts.append({'path': path.name, 'sha256': hashlib.sha256(raw).hexdigest()})
assert frozen is not None
for item in frozen['files'] + frozen['protected_files']:
    raw = (ROOT / item['path']).read_bytes()
    assert len(raw) == item['bytes'], item['path']
    assert hashlib.sha256(raw).hexdigest() == item['sha256'], item['path']
snapshot = BASE / 'futures-review-565'
manifest = json.loads((snapshot / 'manifest.json').read_text())
for item in manifest['files']:
    assert hashlib.sha256((ROOT / item['snapshot']).read_bytes()).hexdigest() == item['sha256']
assert hashlib.sha256((snapshot / 'changes.patch').read_bytes()).hexdigest() == manifest['diff_sha256']
report = {
    'status': 'passed',
    'scope': 'ticket11_progress_only_not_acceptance',
    'head': head,
    'source_version': 'futures-579',
    'tests': '45 passed in 71.13s; tests/adapters/test_futures_inputs.py only',
    'typecheck': '93 source files; src/pring_cycle',
    'receipts': receipts,
    'frozen_files': len(frozen['files']),
    'protected_files': len(frozen['protected_files']),
    'environment_equal': True,
    'review_snapshot_565_unchanged': True,
    'ticket_complete': False,
    'unresolved': [
        'later PUBLIC conflict resolution and equivalent-value/time representation controls',
        'evidence and session negative/control coverage',
        'review-stage local validation duplication',
        'two-axis final review, related and independent HEAD validation, commit',
        'real source certification; later tickets and final default suite',
    ],
}
with (BASE / 'verification-futures-progress-580.json').open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False))
