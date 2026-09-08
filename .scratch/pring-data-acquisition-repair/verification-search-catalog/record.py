"""One-time search catalog checkpoint; final project regression remains open."""
from pathlib import Path
import hashlib
import json
import zipfile

output = Path(__file__).resolve().parent
root = output.parent
logs = sorted(root.glob('verification-search-catalog-*.txt')) + sorted(output.glob('*.txt'))
records = []
archive = output / 'original-logs.zip'
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as saved:
    for path in logs:
        raw = path.read_bytes()
        saved.writestr(path.relative_to(root).as_posix(), raw)
        encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
        content = raw.decode(encoding).replace('\r\n', '\n').encode('utf-8')
        path.write_bytes(content)
        records.append({'path': path.relative_to(root).as_posix(),
                        'original_sha256': hashlib.sha256(raw).hexdigest(),
                        'sha256': hashlib.sha256(content).hexdigest()})
assert '213 passed in 999.04s' in (root / 'verification-search-catalog-related-01.txt').read_text()
assert '6 passed, 112 deselected in 11.56s' in (root / 'verification-search-catalog-review-green-01.txt').read_text()
assert 'All checks passed!' in (output / 'ruff.txt').read_text()
assert 'Success: no issues found in 85 source files' in (output / 'mypy-final.txt').read_text()
fingerprint = json.loads((output / 'source-during-related.json').read_text(encoding='utf-8-sig'))
assert fingerprint['matched_source_files'] == 84
record = {
    'base_commit': '087b9a8250b11d3f72cde093c445baa61c755996',
    'status': 'implementation_checkpoint_full_gate_open', 'goal_complete': False,
    'related': {'passed': 213, 'failed': 0, 'seconds': 999.04},
    'new_cases': {'passed': 6, 'failed': 0, 'seconds': 11.56},
    'review_remaining': {'spec': 0, 'standards': 0},
    'mypy_checked_files': 85, 'installed_source_matches': 84, 'full_gate_passed': False,
    'actual_search_requests': 0, 'actual_model_qualification_checks': 0,
    'actual_source_certifications': 0, 'actual_candidate_models': 0,
    'actual_ai_outputs': 0, 'actual_cutovers': 0, 'production_writes': 0,
    'paired_search_samples': 0, 'model_usable_search_completion_rate': None,
    'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'records': records,
}
with (output / 'checkpoint.json').open('x', encoding='utf-8', newline='\n') as handle:
    json.dump(record, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
print(json.dumps({'archived_logs': len(records), 'related_passed': 213, 'full_gate_passed': False}))
