"""Build an independent HEAD plus ticket 11 source delta; exclude earlier WIP."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
import tarfile
import tempfile

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
PARENT = Path('/home/tywin/.cache/pring-cycle/verification/futures-commit-590')
TREE = PARENT / 'tree'
assert not PARENT.exists()
TREE.mkdir(parents=True)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == '5e186f740be3d275cba5664a13ef0290e6a57916'
archive = subprocess.Popen(['git', 'archive', head], cwd=ROOT, stdout=subprocess.PIPE)
assert archive.stdout is not None
with tarfile.open(fileobj=archive.stdout, mode='r|') as stream:
    stream.extractall(TREE, filter='data')
assert archive.wait() == 0
manifest = json.loads((BASE / 'futures-review-589/manifest.json').read_text())
records = []
patch = []
with tempfile.TemporaryDirectory(dir=PARENT) as temporary:
    for entry in manifest['files']:
        name = entry['source']
        target = TREE / name
        original = target.read_bytes() if target.exists() else b''
        snapshot = ROOT / entry['snapshot']
        current = snapshot.read_bytes()
        assert hashlib.sha256(current).hexdigest() == entry['sha256']
        assert current == (ROOT / name).read_bytes()
        if entry['baseline'] is None:
            assert not original
            merged = current
        else:
            paths = [Path(temporary) / item for item in ('head', 'baseline', 'current')]
            old = (BASE / entry['baseline']).read_bytes()
            for path, raw in zip(paths, (original, old, current), strict=True):
                path.write_bytes(raw)
            result = subprocess.run(['git', 'merge-file', '-p', '--diff3', *map(str, paths)], capture_output=True)
            assert result.returncode == 0, result.stdout.decode()
            merged = result.stdout
        compile(merged, name, 'exec')
        target.write_bytes(merged)
        records.append({'path': name, 'baseline': entry['baseline'], 'snapshot': entry['snapshot'], 'sha256': hashlib.sha256(merged).hexdigest()})
        patch.extend(difflib.unified_diff(original.decode().splitlines(True), merged.decode().splitlines(True), fromfile='a/' + name if entry['baseline'] else '/dev/null', tofile='b/' + name))
preview = BASE / 'futures-index-preview-590.patch'
assert not preview.exists()
preview.write_text(''.join(patch))
record = {'base_head': head, 'tree': str(TREE), 'method': 'HEAD plus own538 delta; earlier WIP excluded; conflict-free three-way transplant', 'files': records, 'patch': preview.name, 'patch_sha256': hashlib.sha256(preview.read_bytes()).hexdigest()}
with (BASE / 'futures-preview-preparation-590.json').open('x') as stream:
    json.dump(record, stream, indent=2)
print(json.dumps({'tree': str(TREE), 'owned_files': len(records), 'patch_bytes': preview.stat().st_size, 'patch_sha256': record['patch_sha256']}))
