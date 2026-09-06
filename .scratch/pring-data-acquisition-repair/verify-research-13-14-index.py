"""Verify staged original bytes and immutable research reports; no network or runtime writes."""
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
expected = {
    13: 'dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1',
    14: '1bad5c100b8996dfa1286da712c723211b9640d8cc98a1e24cdec8647bedf82b',
}
results = []
for ticket, report_hash in expected.items():
    evidence = folder / f'evidence-{ticket}'
    files = (evidence / 'delivery-files.txt').read_text(encoding='utf-8').splitlines()
    assert len(files) == {13: 71, 14: 61}[ticket]
    for relative in files:
        path = (repo / relative).resolve()
        assert path.is_relative_to(folder) and path.is_file(), relative
    originals = [p for p in evidence.iterdir() if re.fullmatch('[0-9a-f]{64}', p.name)]
    report = folder / f'research-{ticket}.md'
    assert hashlib.sha256(report.read_bytes()).hexdigest() == report_hash
    for path in [*originals, report]:
        relative = path.relative_to(repo).as_posix()
        staged = subprocess.check_output(['git', 'show', ':' + relative], cwd=repo)
        assert staged == path.read_bytes(), relative
        if path != report:
            assert hashlib.sha256(staged).hexdigest() == path.name, relative
    results.append({'ticket': ticket, 'report_sha256': report_hash,
                    'exact_staged_original_files': len(originals),
                    'original_bytes': sum(p.stat().st_size for p in originals),
                    'delivery_files': len(files)})
result = {'verified_at': datetime.now(UTC).isoformat(), 'results': results,
          'production_writes': 0, 'network_requests': 0, 'new_certifications': 0}
(folder / 'research-13-14-index-verification.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
