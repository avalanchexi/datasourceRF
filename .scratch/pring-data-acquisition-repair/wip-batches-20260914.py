"""Commit pre-existing uncommitted work in file-disjoint batches, each verified on its own HEAD checkout.

prepare <batch>                     create checkout at HEAD and copy the batch files from the workspace
run <batch> <name> <kind> [args]    build a wheel from the checkout, install it, run <kind> in the checkout
"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

WORKSPACE = Path('/mnt/d/cursor/datasourceRF')
RECORDS = WORKSPACE / '.scratch/pring-data-acquisition-repair'
TASK = Path('/home/tywin/.cache/pring-cycle/verification/wip-batches-20260914')
PYTHON = TASK / 'venv/bin/python'
BATCHES = {
    'a-worker-lifetime': [
        'src/pring_cycle/storage.py',
        'src/pring_cycle/worker.py',
        'tests/e2e/test_local_runtime_cli.py',
        'tests/integration/test_worker_database_lifetime.py',
        'tests/fixtures/worker_heartbeat_shutdown.py',
        'tests/fixtures/worker_sqlite_lifetime.py',
    ],
    'b-report-timing': [
        'src/pring_cycle/reports.py',
        'tests/reports/test_report_boundary.py',
    ],
    'c-registered-consumers': [
        'src/pring_cycle/candidate_admission.py',
        'src/pring_cycle/context_projection.py',
        'src/pring_cycle/context_replay_scope.py',
        'src/pring_cycle/evidence.py',
        'src/pring_cycle/interbank_evidence.py',
        'src/pring_cycle/metric_contracts.py',
        'src/pring_cycle/model_evaluation.py',
        'src/pring_cycle/model_outputs.py',
        'src/pring_cycle/official_context.py',
        'src/pring_cycle/search_evidence.py',
        'src/pring_cycle/source_contract_review.py',
        'src/pring_cycle/treasury_context.py',
        'src/pring_cycle/tushare_context.py',
        'tests/models/test_candidate_admission.py',
        'tests/models/test_candidate_replay.py',
        'tests/models/test_capacity_historical_contract.py',
    ],
    'd-ticket19': [
        'src/pring_cycle/acquisition.py',
        'src/pring_cycle/commodity_basket.py',
        'src/pring_cycle/context_projection.py',
        'src/pring_cycle/evidence.py',
        'src/pring_cycle/futures_inputs.py',
        'src/pring_cycle/interbank_evidence.py',
        'src/pring_cycle/model_evaluation.py',
        'src/pring_cycle/models.py',
        'src/pring_cycle/official_context.py',
        'src/pring_cycle/warrant_inputs.py',
        'tests/integration/test_inventory_period_alignment.py',
        'tests/models/test_isolated_lifecycle.py',
    ],
    'e-ticket17': [
        'src/pring_cycle/commodity_basket.py',
        'src/pring_cycle/futures_inputs.py',
        'src/pring_cycle/market_breadth.py',
        'src/pring_cycle/read_scope.py',
        'src/pring_cycle/worker.py',
        'tests/integration/test_worker_registered_catalog.py',
    ],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): sha(p)
        for folder in ('src', 'tests')
        for p in (root / folder).rglob('*')
        if p.is_file() and '__pycache__' not in p.parts
    }


def prepare(batch: str) -> None:
    checkout = TASK / batch / 'checkout'
    assert not checkout.exists(), checkout
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WORKSPACE, text=True).strip()
    checkout.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'worktree', 'add', '--detach', str(checkout), head], cwd=WORKSPACE, check=True)
    files = {}
    for name in BATCHES[batch]:
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / name, target)
        files[name] = sha(target)
    subprocess.run(['git', 'add', '--', *BATCHES[batch]], cwd=checkout, check=True)
    patch = subprocess.check_output(['git', 'diff', '--cached', '--binary'], cwd=checkout)
    (TASK / batch / 'batch.patch').write_bytes(patch)
    record = {
        'batch': batch, 'head': head, 'files': files,
        'patch_sha256': hashlib.sha256(patch).hexdigest(),
        'changed_paths_are_exactly_batch': sorted(
            line[3:] for line in subprocess.check_output(
                ['git', 'status', '--porcelain', '--untracked-files=all'], cwd=checkout, text=True
            ).splitlines()
        ) == sorted(files),
        'prepared_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out = RECORDS / f'verification-wip-20260914-{batch}-prepare.json'
    out.write_text(json.dumps(record, indent=2))
    print(json.dumps({k: v for k, v in record.items() if k != 'files'}, indent=2))


def run(batch: str, name: str, kind: str, args: list[str]) -> int:
    root = TASK / batch / 'checkout'
    record_path = RECORDS / f'verification-wip-20260914-{batch}-{name}.json'
    log_path = record_path.with_suffix('.txt')
    assert not record_path.exists() and not log_path.exists(), record_path
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(TASK), PIP_CACHE_DIR=str(TASK / 'pip-cache'))
    env['PATH'] = str(TASK / 'venv/bin') + os.pathsep + env['PATH']

    def dependencies() -> str:
        return subprocess.check_output([str(PYTHON), '-c',
            'import importlib.metadata,json; print(json.dumps(sorted((d.metadata["Name"],d.version) '
            'for d in importlib.metadata.distributions())))'], env=env, text=True).strip()

    before = tree(root)
    source = {k: v for k, v in before.items() if k.startswith('src/')}
    built = TASK / 'built.json'
    if not built.exists() or json.loads(built.read_text()) != source:
        wheels = TASK / 'wheel'
        shutil.rmtree(wheels, ignore_errors=True)
        subprocess.run([str(PYTHON), '-m', 'hatchling', 'build', '-t', 'wheel', '-d', str(wheels)],
                       cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)
        wheel = next(wheels.glob('*.whl'))
        subprocess.run([str(PYTHON), '-m', 'pip', 'install', '--no-deps', '--force-reinstall', str(wheel)],
                       cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)
        built.write_text(json.dumps(source))
    installed = TASK / 'venv/lib/python3.12/site-packages/pring_cycle'

    def installed_matches() -> bool:
        return all(
            p.read_bytes() == (installed / p.relative_to(root / 'src/pring_cycle')).read_bytes()
            for p in (root / 'src/pring_cycle').rglob('*')
            if p.is_file() and '__pycache__' not in p.parts
        )

    assert installed_matches()
    dependency_versions = dependencies()
    command = [str(PYTHON), '-m', kind]
    if kind == 'pytest':
        command += ['-q', '--tb=short', '-p', 'no:cacheprovider', '--basetemp=' + str(TASK / batch / name)]
    if kind == 'mypy':
        command += ['--cache-dir=' + str(TASK / 'mypy-cache')]
    if kind == 'ruff':
        env['RUFF_CACHE_DIR'] = str(TASK / 'ruff-cache')
    command += args
    record = {'batch': batch, 'command': command, 'root': str(root),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'running', 'inputs': before, 'dependency_versions': dependency_versions}
    record_path.write_text(json.dumps(record, indent=2))
    start = time.monotonic()
    with log_path.open('x') as log:
        result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    record.update(
        exit_code=result.returncode, duration_seconds=time.monotonic() - start,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        inputs_unchanged=tree(root) == before,
        dependencies_unchanged=dependencies() == dependency_versions,
        installed_source_unchanged=installed_matches(),
        log_sha256=sha(log_path),
    )
    ok = all(record[k] for k in ('inputs_unchanged', 'dependencies_unchanged', 'installed_source_unchanged'))
    record['status'] = 'passed' if result.returncode == 0 and ok else 'failed'
    record_path.write_text(json.dumps(record, indent=2))
    print(log_path.read_text()[-4000:])
    print(json.dumps({k: v for k, v in record.items() if k not in ('inputs', 'command', 'dependency_versions')}))
    return 0 if record['status'] == 'passed' else 1


def augment(batch: str, paths: list[str]) -> None:
    """Add untracked fixture files that the batch tests read; record every copied file."""
    checkout = TASK / batch / 'checkout'
    copied = {}
    for name in paths:
        source = WORKSPACE / name
        for item in ([source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file())):
            if '__pycache__' in item.parts:
                continue
            relative = str(item.relative_to(WORKSPACE))
            target = checkout / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)
            copied[relative] = sha(target)
    subprocess.run(['git', 'add', '-f', '--', *copied], cwd=checkout, check=True)
    patch = subprocess.check_output(['git', 'diff', '--cached', '--binary'], cwd=checkout)
    (TASK / batch / 'batch.patch').write_bytes(patch)
    out = RECORDS / f'verification-wip-20260914-{batch}-augment-{len(list(RECORDS.glob(f"verification-wip-20260914-{batch}-augment-*.json")))+1}.json'
    out.write_text(json.dumps({'batch': batch, 'copied': copied,
                               'patch_sha256': hashlib.sha256(patch).hexdigest()}, indent=2))
    print(out.name, len(copied), 'files')


if __name__ == '__main__':
    action, batch, *rest = sys.argv[1:]
    if action == 'prepare':
        prepare(batch)
    elif action == 'augment':
        augment(batch, rest)
    else:
        sys.exit(run(batch, rest[0], rest[1], rest[2:]))
