"""Project only ticket 12 changes onto its fixed HEAD; preserve other workspace edits."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/mnt/d/cursor/datasourceRF')
RECORDS = ROOT / '.scratch/pring-data-acquisition-repair'
TASK = Path('/home/tywin/.cache/pring-cycle/verification/commodity-resume-20260913')
BASE = '9a36df502fbc345b3041e39364430aaf3f676910'


def transplant(original, baseline, current):
    before, after = baseline.splitlines(keepends=True), current.splitlines(keepends=True)
    result = original
    for tag, i, j, a, b in reversed(difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes()):
        if tag == 'equal':
            continue
        old, new = ''.join(before[i:j]), ''.join(after[a:b])
        if old and old.strip():
            assert result.count(old) == 1, ('replace anchor', old)
            result = result.replace(old, new, 1)
            continue
        if not old.strip() and not new.strip():
            continue
        for width in range(4, 0, -1):
            following = ''.join(before[j:j + width])
            if following.strip() and result.count(following) == 1:
                result = result.replace(following, new + following, 1)
                break
            preceding = ''.join(before[max(0, i-width):i])
            if preceding.strip() and result.count(preceding) == 1:
                result = result.replace(preceding, preceding + new, 1)
                break
        else:
            raise ValueError(('insert anchor', old, new))
    ast.parse(result)
    return result


files = [
 'src/pring_cycle/'+name+'.py' for name in (
  'commodity_basket', 'futures_inputs', 'evidence', 'metric_contracts',
  'source_contract_review', 'search_evidence', 'model_evaluation')
] + ['tests/adapters/test_commodity_basket.py', 'tests/models/test_registered_commodity.py']
patch = []
projected = TASK / 'projected'
for name in files:
    read = subprocess.run(['git','show',BASE+':'+name],cwd=ROOT,capture_output=True,text=True)
    original = read.stdout if read.returncode == 0 else ''
    current = (ROOT/name).read_text()
    if not original or name.endswith('/futures_inputs.py'):
        content = current
    elif name.endswith('/evidence.py'):
        content = original.replace('        from pring_cycle.source_adapters import CORE_API_IDENTITIES, parse_core_acquisition',
          '        from pring_cycle.commodity_basket import require_commodity_results\n        from pring_cycle.source_adapters import CORE_API_IDENTITIES, parse_core_acquisition',1)
        content = content.replace('        originals: dict[tuple[str, str], dict[str, float]] = {}',
          '        require_commodity_results(self._database_path, claims)\n        originals: dict[tuple[str, str], dict[str, float]] = {}',1)
    else:
        baseline = (RECORDS/('commodity-base-614-'+Path(name).name+'.txt')).read_text()
        content = transplant(original, baseline, current)
    path = projected/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content)
    patch.extend(difflib.unified_diff(original.splitlines(keepends=True),content.splitlines(keepends=True),
      fromfile='a/'+name if original else '/dev/null',tofile='b/'+name))
patch_path = TASK/'ticket12.patch'
patch_path.write_text(''.join(patch))
print(json.dumps({'patch':str(patch_path),'sha256':hashlib.sha256(patch_path.read_bytes()).hexdigest(),'files':files},indent=2))
