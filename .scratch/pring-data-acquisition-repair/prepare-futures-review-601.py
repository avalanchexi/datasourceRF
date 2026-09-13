"""Freeze only ticket 11's delta against the recorded pre-ticket worktree."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess

ROOT = Path('/mnt/d/cursor/datasourceRF')
BASE = ROOT / '.scratch/pring-data-acquisition-repair'
DEST = BASE / 'futures-review-601'
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head == '5e186f740be3d275cba5664a13ef0290e6a57916'
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT)
assert (ROOT / 'src/pring_cycle/cli.py').read_bytes() == (BASE / 'futures-base-538-cli.py.txt').read_bytes()
DEST.mkdir()
records = []
patch = []
for name, baseline in (
    ('src/pring_cycle/futures_inputs.py', None),
    ('src/pring_cycle/tushare_context.py', 'futures-base-538-tushare_context.py.txt'),
    ('tests/adapters/test_futures_inputs.py', None),
):
    raw = (ROOT / name).read_bytes()
    old = (BASE / baseline).read_bytes() if baseline else b''
    snapshot = DEST / Path(name).name
    snapshot.write_bytes(raw)
    records.append({'source': name, 'baseline': baseline, 'snapshot': str(snapshot.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest()})
    patch.extend(difflib.unified_diff(old.decode().splitlines(True), raw.decode().splitlines(True), fromfile='a/' + name if baseline else '/dev/null', tofile='b/' + name))
diff = ''.join(patch)
assert diff and '+    def acquire_futures_inputs(' in diff
(DEST / 'changes.patch').write_text(diff)
record = {'base_head': head, 'working_tree_review': True, 'commits': [], 'files': records, 'diff_sha256': hashlib.sha256(diff.encode()).hexdigest()}
(DEST / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'files': len(records), 'diff_bytes': len(diff.encode()), 'diff_sha256': record['diff_sha256']}))
