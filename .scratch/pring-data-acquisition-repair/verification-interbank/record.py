"""One-time implementation checkpoint. Does not close the full regression gate."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parent.parent
output = root / 'verification-interbank'
logs = sorted(root.glob('verification-interbank-*.txt')) + sorted(output.glob('*.txt'))
archive = output / 'original-logs.zip'
records = []
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
assert '156 passed in 244.16s' in (root / 'verification-interbank-related-01.txt').read_text()
assert '12 passed, 100 deselected in 40.94s' in (root / 'verification-interbank-review-green-01.txt').read_text()
assert 'All checks passed!' in (output / 'ruff.txt').read_text()
fingerprint = json.loads((output / 'source-during-related.json').read_text(encoding='utf-8-sig'))
assert fingerprint['matched_source_files'] == 84
record = {
    'base_commit': '0452aca80ce601ee105c824d6cee3f707439c39b',
    'status': 'implementation_checkpoint_full_gate_open', 'goal_complete': False,
    'related': {'passed': 156, 'failed': 0, 'seconds': 244.16},
    'interbank_cases': {'passed': 12, 'failed': 0, 'seconds': 40.94},
    'review_remaining': {'spec': 0, 'standards': 0},
    'mypy': {'checked_files': 85, 'exit_code': 0,
             'evidence': 'tool session 1169 final output: Success: no issues found in 85 source files'},
    'installed_source_matches': 84, 'full_gate_passed': False,
    'actual_source_certifications': 0, 'actual_candidate_models': 0,
    'actual_ai_outputs': 0, 'actual_cutovers': 0, 'production_writes': 0,
    'paired_search_samples': 0, 'model_usable_search_completion_rate': None,
    'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'records': records,
}
with (output / 'checkpoint.json').open('x', encoding='utf-8', newline='\n') as handle:
    json.dump(record, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
print(json.dumps({'archived_logs': len(records), 'related_passed': 156, 'full_gate_passed': False}))
