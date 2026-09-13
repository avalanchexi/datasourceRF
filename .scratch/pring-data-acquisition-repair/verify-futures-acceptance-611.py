"""Verify ticket 11 software evidence, not source certification or the full goal."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == '5e186f740be3d275cba5664a13ef0290e6a57916'
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT)
records = []
frozen = None
environment = None
for name in ('public-order-green-607', 'types-607', 'lint-607', 'format-607', 'related-610'):
    path = BASE / f'verification-futures-{name}.json'
    raw = path.read_bytes()
    record = json.loads(raw)
    assert record['status'] == 'passed' and record['test_exit_code'] == 0
    assert record['helper_inputs_unchanged'] and record['before'] == record['after']
    if frozen is None:
        frozen, environment = record['frozen_inputs'], record['after']
    assert record['frozen_inputs'] == frozen and record['after'] == environment
    log = (BASE / record['log']['path']).read_bytes()
    assert len(log) == record['log']['bytes']
    assert hashlib.sha256(log).hexdigest() == record['log']['sha256']
    records.append({'path': path.name, 'sha256': hashlib.sha256(raw).hexdigest()})
assert frozen is not None
for item in frozen['files'] + frozen['protected_files']:
    raw = (ROOT / item['path']).read_bytes()
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], item['path']
review = json.loads((BASE / 'futures-review-608/manifest.json').read_bytes())
assert review['base_head'] == head and review['commits'] == []
for item in review['files']:
    raw = (ROOT / item['snapshot']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    assert raw == (ROOT / item['source']).read_bytes()
assert hashlib.sha256((BASE / 'futures-review-608/changes.patch').read_bytes()).hexdigest() == review['diff_sha256']
reviews = []
for axis, expected in (
    ('standards', '2b20efeaade5de2707687d064ee0917d884e8b430a85b4246615439029a484a9'),
    ('spec', 'f144c237d7ab1e336cbdf12644642bfc41db1b6f300e8ed20327afc4651468fd'),
):
    path = BASE / f'review-futures-{axis}-608.md'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    reviews.append({'path': path.name, 'sha256': expected})
preparation = json.loads((BASE / 'futures-preview-preparation-609.json').read_bytes())
independent_path = BASE / 'verification-futures-preview-609.json'
independent = json.loads(independent_path.read_bytes())
assert preparation['base_head'] == head
assert independent['status'] == 'passed'
assert independent['before'] == independent['after']
assert all(step['exit_code'] == 0 for step in independent['steps'])
assert {step['name'] for step in independent['steps']} == {'imports', 'format', 'build', 'install', 'lint', 'typecheck', 'tests'}
for step in independent['steps']:
    assert hashlib.sha256((BASE / step['log']).read_bytes()).hexdigest() == step['log_sha256']
tree = Path(preparation['tree'])
for item in preparation['files']:
    assert hashlib.sha256((tree / item['path']).read_bytes()).hexdigest() == item['sha256']
    assert independent['owned_files'][item['path']] == item['sha256']
for name, expected in independent['after']['files'].items():
    assert hashlib.sha256((tree / name).read_bytes()).hexdigest() == expected
assert hashlib.sha256((BASE / preparation['patch']).read_bytes()).hexdigest() == preparation['patch_sha256']
assert hashlib.sha256(Path(independent['wheel']['path']).read_bytes()).hexdigest() == independent['wheel']['sha256']
assert environment is not None
assert independent['after']['environment']['dependencies'] == environment['dependencies']
assert independent['after']['environment']['python'] == environment['python'] == '3.12.12'
assert independent['driver_sha256'] == hashlib.sha256((BASE / 'run-futures-preview-609.py').read_bytes()).hexdigest()
tests = {name: (BASE / f'verification-futures-{name}.txt').read_text().strip().splitlines()[-1] for name in ('public-order-green-607', 'related-610')}
independent_tests = (BASE / 'verification-futures-preview-tests-609.txt').read_text().strip().splitlines()[-1]
report = {
    'status': 'passed', 'scope': 'ticket11_software_only', 'base_head': head,
    'source_version': 'futures-607', 'tests': tests, 'independent_tests': independent_tests,
    'receipts': records, 'reviews': reviews,
    'standards_hard_violations': 0, 'standards_nonblocking_p3_suggestions': 2, 'spec_software_findings': 0,
    'frozen_files': len(frozen['files']), 'protected_files': len(frozen['protected_files']),
    'environment_equal': True, 'independent_head_plus_own_delta': preparation,
    'independent_receipt_sha256': hashlib.sha256(independent_path.read_bytes()).hexdigest(),
    'source_certification_complete': False, 'full_goal_complete': False,
    'remaining': ['real futures source certification and historical PUBLIC evidence', 'ticket12 commodity selection and registered derived contracts', 'M3-M6 and final default suite', 'ticket23 remains deferred'],
}
with (BASE / 'verification-futures-acceptance-611.json').open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps({k: report[k] for k in ('status', 'scope', 'tests', 'independent_tests', 'frozen_files', 'protected_files')}, ensure_ascii=False))
