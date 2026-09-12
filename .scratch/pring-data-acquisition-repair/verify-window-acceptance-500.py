from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
PREVIEW = Path('/home/tywin/.cache/pring-cycle/verification/window-commit-496/tree')
OUTPUT = BASE / 'verification-window-acceptance-500.json'
assert not OUTPUT.exists()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == '7272057fcbc5e1bd31c0673ead9f8dc25485e566'
record = {'base_head': head, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'checks': {}, 'reviews': {}, 'scope': 'Ticket09 software only; real certification, full-market capacity, M3-M6 and final default suite remain open.'}
fingerprints = []
for label in ('family-495', 'related-497', 'types-493', 'lint-493'):
    path = BASE / ('verification-window-' + label + '.json')
    raw = path.read_bytes()
    item = json.loads(raw)
    assert item['status'] == 'passed' and item['test_exit_code'] == 0, label
    assert item['before'] == item['after'] and item['helper_inputs_unchanged'], label
    assert all(hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest for name, digest in item['helper_inputs_before'].items())
    fingerprints.append(item['frozen_inputs'])
    log = BASE / item['log']['path']
    assert hashlib.sha256(log.read_bytes()).hexdigest() == item['log']['sha256']
    for source in item['frozen_inputs']['files'] + item['frozen_inputs']['protected_files']:
        content = (ROOT / source['path']).read_bytes()
        assert len(content) == source['bytes'] and hashlib.sha256(content).hexdigest() == source['sha256'], source['path']
    passed = re.search(r'(\d+) passed', log.read_text())
    record['checks'][label] = {'receipt': path.name, 'receipt_sha256': hashlib.sha256(raw).hexdigest(), 'log_sha256': item['log']['sha256'], 'exit_code': 0, 'passed': int(passed.group(1)) if passed else None}
assert all(item == fingerprints[0] for item in fingerprints)
assert record['checks']['family-495']['passed'] == 37
preview_file = BASE / 'verification-window-preview-496.json'
preview_raw = preview_file.read_bytes()
preview = json.loads(preview_raw)
assert preview['status'] == 'passed' and preview['before'] == preview['after']
for step in preview['steps']:
    assert step['exit_code'] == 0
    assert hashlib.sha256((BASE / step['log']).read_bytes()).hexdigest() == step['log_sha256']
for name, digest in preview['owned_files'].items():
    assert hashlib.sha256((PREVIEW / name).read_bytes()).hexdigest() == digest
for name, digest in preview['after']['files'].items():
    assert hashlib.sha256((PREVIEW / name).read_bytes()).hexdigest() == digest
preview_test = next(step for step in preview['steps'] if step['name'] == 'tests')
passed = re.search(r'(\d+) passed', (BASE / preview_test['log']).read_text())
assert passed and int(passed.group(1)) == 175
record['checks']['preview-496'] = {'receipt': preview_file.name, 'receipt_sha256': hashlib.sha256(preview_raw).hexdigest(), 'passed': 175, 'exit_code': 0, 'owned_files': preview['owned_files']}
preparation = json.loads((BASE / 'window-preview-preparation-496.json').read_text())
patch = BASE / preparation['patch']
assert hashlib.sha256(patch.read_bytes()).hexdigest() == preparation['patch_sha256']
assert all(hashlib.sha256((PREVIEW / item['path']).read_bytes()).hexdigest() == item['sha256'] for item in preparation['files'])
for label in ('spec-495', 'standards-495', 'spec-498', 'standards-498'):
    path = BASE / ('review-window-' + label + '.md')
    record['reviews'][label] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
record['review_result'] = {'new_hard_findings': 0, 'retained_judgment_smells': 1, 'smell': '27 scenarios share a long parameterized test; not an automatic commit gate.'}
record['patch'] = {'path': patch.name, 'sha256': preparation['patch_sha256']}
record['frozen_inputs'] = fingerprints[0]
record['status'] = 'passed'
OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'checks': {name: item['passed'] for name, item in record['checks'].items()}, 'owned_files': len(preview['owned_files']), 'output': str(OUTPUT)}))
