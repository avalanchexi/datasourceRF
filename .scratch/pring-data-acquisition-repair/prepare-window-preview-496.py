from pathlib import Path
import difflib
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
PARENT = Path('/home/tywin/.cache/pring-cycle/verification/window-commit-496')
TREE = PARENT / 'tree'
assert not PARENT.exists()
TREE.mkdir(parents=True)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == '7272057fcbc5e1bd31c0673ead9f8dc25485e566'
archive = subprocess.Popen(['git', 'archive', head], cwd=ROOT, stdout=subprocess.PIPE)
assert archive.stdout is not None
with tarfile.open(fileobj=archive.stdout, mode='r|') as stream:
    stream.extractall(TREE, filter='data')
assert archive.wait() == 0
review = json.loads((BASE / 'window-review-inputs-495.json').read_text())
records = []
patch = []
with tempfile.TemporaryDirectory(dir=PARENT) as temporary:
    for entry in review['files']:
        name = entry['path']
        target = TREE / name
        original = target.read_bytes()
        old = (BASE / entry['baseline']).read_bytes()
        snapshot = BASE / entry['snapshot']
        current = snapshot.read_bytes()
        assert hashlib.sha256(current).hexdigest() == entry['sha256']
        conflicts = 0
        if name.startswith('tests/'):
            prefix = old.rstrip() + b'\n\n\n'
            assert current.startswith(prefix)
            merged = original.rstrip() + b'\n\n\n' + current[len(prefix):]
        else:
            paths = [Path(temporary) / item for item in ('head', 'baseline', 'current')]
            for path, raw in zip(paths, (original, old, current), strict=True):
                path.write_bytes(raw)
            result = subprocess.run(['git', 'merge-file', '-p', '--diff3', *map(str, paths)], capture_output=True)
            assert result.returncode in (0, 1), result.stderr
            text = result.stdout.decode()
            if result.returncode:
                assert Path(name).name in {'search_evidence.py', 'model_evaluation.py'}
                match = re.search(r'^<<<<<<< .*?\n(.*?)^\|\|\|\|\|\|\| .*?\n(.*?)^=======\n(.*?)^>>>>>>> .*?\n', text, re.M | re.S)
                assert match and text.count('<<<<<<<') == 1
                assert 'INTERBANK_METRICS' not in match.group(1)
                assert 'INTERBANK_METRICS' in match.group(2) and 'INTERBANK_METRICS' in match.group(3)
                resolved = match.group(3).replace('from pring_cycle.interbank_evidence import INTERBANK_METRICS, interbank_claims_matching_acquisitions\n', '')
                text = text[:match.start()] + resolved + text[match.end():]
                conflicts = 1
            merged = text.encode()
        compile(merged, name, 'exec')
        target.write_bytes(merged)
        records.append({'path': name, 'baseline': entry['baseline'], 'snapshot': entry['snapshot'], 'sha256': hashlib.sha256(merged).hexdigest(), 'adjacent_import_conflicts_resolved': conflicts})
        patch.extend(difflib.unified_diff(original.decode().splitlines(True), merged.decode().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
preview = BASE / 'window-index-preview-496.patch'
assert not preview.exists()
preview.write_text(''.join(patch))
record = {'base_head': head, 'tree': str(TREE), 'method': 'HEAD plus own422/476 delta; prior WIP excluded, only two adjacent interbank imports resolved', 'files': records, 'patch': preview.name, 'patch_sha256': hashlib.sha256(preview.read_bytes()).hexdigest()}
(BASE / 'window-preview-preparation-496.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'tree': str(TREE), 'owned_files': len(records), 'patch_bytes': preview.stat().st_size, 'patch_sha256': record['patch_sha256']}))
