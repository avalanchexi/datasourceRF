"""Run existing pytest/typecheck commands with frozen inputs in the native EIA environment."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
NATIVE = Path('/home/tywin/.cache/pring-cycle/verification/eia-catalog-20260912-301')
PYTHON = NATIVE / 'venv/bin/python'
ALLOWED_CHANGES = {
    'src/pring_cycle/market_amount.py',
    'src/pring_cycle/evidence.py',
    'src/pring_cycle/market_breadth.py',
    'src/pring_cycle/metric_contracts.py',
    'src/pring_cycle/model_evaluation.py',
    'src/pring_cycle/search_evidence.py',
    'src/pring_cycle/tushare_context.py',
    'src/pring_cycle/source_contract_review.py',
    'src/pring_cycle/eia_context.py',
    'src/pring_cycle/eia_html.py',
    'tests/models/test_candidate_admission.py',
}

name, kind, *arguments = sys.argv[1:]
assert re.fullmatch(r'[a-z0-9-]+', name)
assert kind in {'pytest', 'mypy', 'ruff'}
assert Path.cwd() == ROOT
prefix = BASE / ('verification-amount-' + name)
terminal = prefix.with_suffix('.json')
log = prefix.with_suffix('.txt')
assert not terminal.exists() and not log.exists()
native_environment = json.loads((BASE / 'verification-eia-environment-301.json').read_text())
helper_paths = [Path(__file__), BASE / 'verification-eia-environment-301.json']
helper_hashes = {str(path.relative_to(BASE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in helper_paths}
frozen = json.loads((BASE / 'amount-baseline-502.json').read_text())['frozen_inputs']
for added in ['src/pring_cycle/market_amount.py']:
    if (ROOT / added).exists():
        frozen['files'].append({'path': added, 'bytes': 0, 'sha256': ''})
for item in frozen['files'] + frozen['protected_files']:
    raw = (ROOT / item['path']).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if item['path'] in ALLOWED_CHANGES:
        item.update(bytes=len(raw), sha256=digest)
    else:
        assert len(raw) == item['bytes'] and digest == item['sha256'], item['path']

environment_probe = r'''
import hashlib, importlib.metadata, json, sqlite3, sys, sysconfig
from pathlib import Path
import pring_cycle
root = Path.cwd()
source = root / 'src/pring_cycle'
installed = Path(sysconfig.get_path('purelib')) / 'pring_cycle'
assert Path(pring_cycle.__file__).resolve().parent == installed
names = {p.relative_to(source) for p in source.rglob('*.py')}
assert names == {p.relative_to(installed) for p in installed.rglob('*.py')}
for name in names:
    assert (source / name).read_bytes().replace(b'\r\n', b'\n') == (installed / name).read_bytes().replace(b'\r\n', b'\n'), str(name)
with sqlite3.connect(':memory:') as connection:
    sqlite_source_id = connection.execute('select sqlite_source_id()').fetchone()[0]
print(json.dumps({
    'environment': sys.prefix,
    'python': sys.version.split()[0],
    'base_python_sha256': hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
    'sqlite': sqlite3.sqlite_version,
    'sqlite_source_id': sqlite_source_id,
    'dependencies': {p.metadata['Name']: p.version for p in importlib.metadata.distributions() if p.metadata['Name'].lower() != 'pring-cycle'},
    'installed_sources_matched': len(names),
    'package_files': {p.relative_to(installed).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in installed.rglob('*') if p.is_file() and '__pycache__' not in p.parts},
}))
'''
env = os.environ.copy()
env.pop('PYTHONPATH', None)
env['PYTHONDONTWRITEBYTECODE'] = '1'
temporary = NATIVE / 'tmp'
temporary.mkdir(exist_ok=True)
env['TMPDIR'] = str(temporary)


def snapshot():
    document = json.loads(subprocess.check_output([str(PYTHON), '-c', environment_probe], cwd=ROOT, env=env, text=True))
    assert document['environment'] == native_environment['prefix']
    assert document['dependencies'] == native_environment['dependencies']
    assert document['python'] == '3.12.12'
    for item in frozen['files'] + frozen['protected_files']:
        raw = (ROOT / item['path']).read_bytes()
        assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], item['path']
    return document


command = [str(PYTHON), '-m', kind]
if kind == 'pytest':
    basetemp = NATIVE / name
    assert not basetemp.exists()
    command += ['--basetemp=' + str(basetemp), '-q', '--tb=short']
if kind == 'mypy':
    command += ['--cache-dir=' + str(NATIVE / 'mypy-cache')]
command += arguments
record = {
    'name': name,
    'kind': kind,
    'started_at': datetime.now(timezone.utc).isoformat(),
    'driver_pid': os.getpid(),
    'command': command,
    'frozen_inputs': frozen,
    'helper_inputs_before': helper_hashes,
    'status': 'starting',
    'test_exit_code': None,
}
started = time.monotonic()
try:
    record['before'] = snapshot()
    with log.open('xb') as stream:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    record['test_exit_code'] = completed.returncode
    record['after'] = snapshot()
    assert record['before'] == record['after'], 'environment_changed_during_command'
    record['status'] = 'passed' if completed.returncode == 0 else 'failed'
except Exception as error:
    record['status'] = 'harness_failed'
    record['error'] = f'{type(error).__name__}: {error}'
finally:
    record['helper_inputs_unchanged'] = all(hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest for name, digest in helper_hashes.items())
    if not record['helper_inputs_unchanged']:
        record.update(status='harness_failed', error='verification_helper_changed_during_run')
    record['finished_at'] = datetime.now(timezone.utc).isoformat()
    record['duration_seconds'] = round(time.monotonic() - started, 3)
    record['driver_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if log.exists():
        record['log'] = {'path': log.name, 'bytes': log.stat().st_size, 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    with terminal.open('x') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
print(json.dumps({key: record[key] for key in ('name', 'status', 'test_exit_code', 'duration_seconds')}))
if 'error' in record:
    print(record['error'])
if log.exists():
    print(log.read_text()[-7000:])
raise SystemExit(0 if record['status'] == 'passed' else 1)
