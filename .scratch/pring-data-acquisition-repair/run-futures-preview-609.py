from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
PARENT = Path('/home/tywin/.cache/pring-cycle/verification/futures-commit-609')
TREE = PARENT / 'tree'
VENV = PARENT / 'venv'
SOURCE_VENV = Path('/home/tywin/.cache/pring-cycle/verification/eia-catalog-20260912-301/venv')
assert (BASE / 'futures-preview-preparation-609.json').exists()
assert not VENV.exists()
shutil.copytree(SOURCE_VENV, VENV, symlinks=True)
PYTHON = str(VENV / 'bin/python')
UV = '/home/tywin/.local/bin/uv'
owned = [item['path'] for item in json.loads((BASE / 'futures-preview-preparation-609.json').read_text())['files']]
env = dict(os.environ)
env.pop('PYTHONPATH', None)
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['TMPDIR'] = str(PARENT / 'tmp')
Path(env['TMPDIR']).mkdir()
terminal = BASE / 'verification-futures-preview-609.json'
assert not terminal.exists()
steps = []
record = {'status': 'running', 'steps': steps, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'tree': str(TREE)}


def save():
    terminal.write_text(json.dumps(record, indent=2) + '\n')


def run(name, command):
    started = time.monotonic()
    logfile = BASE / ('verification-futures-preview-' + name + '-609.txt')
    assert not logfile.exists()
    with logfile.open('xb') as stream:
        result = subprocess.run(command, cwd=TREE, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    item = {'name': name, 'command': command, 'cwd': str(TREE), 'exit_code': result.returncode, 'duration_seconds': round(time.monotonic() - started, 3), 'log': logfile.name, 'log_sha256': hashlib.sha256(logfile.read_bytes()).hexdigest()}
    steps.append(item)
    if result.returncode:
        record['status'] = 'failed'
    save()
    print(json.dumps(item), flush=True)
    print(logfile.read_text()[-3500:], flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)


run('imports', [PYTHON, '-m', 'ruff', 'check', '--select', 'I', *owned])
run('format', [PYTHON, '-m', 'ruff', 'format', '--check', *owned])
run('build', [UV, 'build', '--offline', '--wheel', '--out-dir', str(PARENT / 'wheels')])
wheel, = (PARENT / 'wheels').glob('*.whl')
run('install', [UV, 'pip', 'install', '--offline', '--no-deps', '--reinstall', '--python', PYTHON, str(wheel)])
record['wheel'] = {'path': str(wheel), 'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}
probe = r'''
from pathlib import Path
import hashlib, importlib.metadata, json, sys, sysconfig
import pring_cycle
source = Path.cwd() / 'src/pring_cycle'
installed = Path(sysconfig.get_path('purelib')) / 'pring_cycle'
assert Path(pring_cycle.__file__).resolve().parent == installed
paths = {p.relative_to(source) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
installed_paths = {p.relative_to(installed) for p in installed.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
assert paths == installed_paths
for path in paths:
    assert (source / path).read_bytes() == (installed / path).read_bytes(), str(path)
print(json.dumps({'prefix': sys.prefix, 'python': sys.version.split()[0], 'package_files': {str(path): hashlib.sha256((installed / path).read_bytes()).hexdigest() for path in sorted(paths)}, 'dependencies': {p.metadata['Name']: p.version for p in importlib.metadata.distributions() if p.metadata['Name'].lower() != 'pring-cycle'}}))
'''


def snapshot():
    files = sorted(p for directory in ('src', 'tests') for p in (TREE / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files += [TREE / 'pyproject.toml', TREE / 'uv.lock']
    package = json.loads(subprocess.check_output([PYTHON, '-c', probe], cwd=TREE, env=env, text=True))
    expected = json.loads((BASE / 'verification-eia-environment-301.json').read_text())['dependencies']
    assert package['dependencies'] == expected and package['python'] == '3.12.12'
    assert package['prefix'] == str(VENV)
    return {'files': {p.relative_to(TREE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, 'environment': package}


record['before'] = snapshot()
save()
run('lint', [PYTHON, '-m', 'ruff', 'check', *owned])
run('typecheck', [PYTHON, '-m', 'mypy', 'src/pring_cycle'])
run('tests', [PYTHON, '-m', 'pytest', '-q', '--tb=short', 'tests/adapters/test_futures_inputs.py', 'tests/adapters/test_tushare_context.py', 'tests/integration/test_context_acquisition_receipts.py', 'tests/adapters/test_source_history_acquisition.py', '--basetemp', str(PARENT / 'pytest-609')])
record['after'] = snapshot()
assert record['before'] == record['after']
record['status'] = 'passed'
record['owned_files'] = {name: hashlib.sha256((TREE / name).read_bytes()).hexdigest() for name in owned}
save()
print(json.dumps({'status': record['status'], 'owned_files': len(owned), 'steps': len(steps)}), flush=True)
