"""Run frozen wheel-based checks in a task-specific native temporary environment."""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time

ROOT = Path(os.environ.get('COMMODITY_VERIFY_ROOT', '/mnt/d/cursor/datasourceRF'))
TASK = Path('/home/tywin/.cache/pring-cycle/verification/commodity-resume-20260913')
PYTHON = TASK/'venv/bin/python'
RECORDS = Path('/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair')
name, kind, *args = sys.argv[1:]
record_path = RECORDS/('verification-commodity-20260913-'+name+'.json')
log_path = record_path.with_suffix('.txt')
assert not record_path.exists() and not log_path.exists()
env = os.environ.copy()
env.pop('PYTHONPATH', None)
env.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(TASK), PIP_CACHE_DIR=str(TASK/'pip-cache'))
env['PATH'] = str(TASK/'venv/bin')+os.pathsep+env['PATH']

def fingerprint():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src','tests') for p in (ROOT/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}

def dependencies():
    return subprocess.check_output([str(PYTHON), '-c',
        'import importlib.metadata,json; print(json.dumps(sorted((d.metadata["Name"],d.version) for d in importlib.metadata.distributions())))'], env=env, text=True).strip()

before = fingerprint()
dependency_versions = dependencies()
source = {k:v for k,v in before.items() if k.startswith('src/')}
built = TASK/'built.json'
if not built.exists() or json.loads(built.read_text()) != source:
    subprocess.run([str(PYTHON), '-m', 'hatchling', 'build', '-t', 'wheel', '-d', str(TASK/'wheel')], cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    wheel = next((TASK/'wheel').glob('*.whl'))
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--no-deps', '--force-reinstall', str(wheel)], cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    built.write_text(json.dumps(source))
installed = TASK/'venv/lib/python3.12/site-packages/pring_cycle'
for p in (ROOT/'src/pring_cycle').rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:
        assert p.read_bytes() == (installed/p.relative_to(ROOT/'src/pring_cycle')).read_bytes(), p
command = [str(PYTHON), '-m', kind]
if kind == 'pytest': command += ['-q','--tb=short','--basetemp='+str(TASK/name)]
if kind == 'mypy': command += ['--cache-dir='+str(TASK/'mypy-cache')]
if kind == 'ruff': env['RUFF_CACHE_DIR'] = str(TASK/'ruff-cache')
command += args
start = time.monotonic()
record = {'command':command,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs':before,'status':'running','root':str(ROOT),'dependency_versions':dependency_versions}
record_path.write_text(json.dumps(record,indent=2))
with log_path.open('x') as log:
    result = subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
record.update(exit_code=result.returncode,duration_seconds=time.monotonic()-start,
              finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              inputs_unchanged=fingerprint()==before,
              log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest())
record['dependencies_unchanged'] = dependencies() == dependency_versions
record['installed_source_unchanged'] = all(p.read_bytes() == (installed/p.relative_to(ROOT/'src/pring_cycle')).read_bytes() for p in (ROOT/'src/pring_cycle').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
record['status'] = 'passed' if result.returncode==0 and record['inputs_unchanged'] and record['dependencies_unchanged'] and record['installed_source_unchanged'] else 'failed'
record_path.write_text(json.dumps(record,indent=2))
print(log_path.read_text()[-6000:])
print(json.dumps({k:v for k,v in record.items() if k not in ('inputs','command','dependency_versions')}))
sys.exit(0 if record['status']=='passed' else 1)
