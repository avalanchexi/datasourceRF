"""Read-only standard-library evidence verification; never imports the application.

--write-report writes only this new package's delivery list and manifest.
For a fresh installed public-parser replay use prepare.py under the required WSL Python.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / 'p1-official-preparation.md'
DELIVERY = HERE / 'delivery-files.txt'
MANIFEST = HERE / 'delivery-verification.json'


def local_path(value):
    if sys.platform == 'win32' and value.startswith('/home/tywin/'):
        return Path('//wsl.localhost/Ubuntu-22.04') / value.lstrip('/')
    if sys.platform == 'win32' and value.startswith('/mnt/d/'):
        return Path('D:/') / value[len('/mnt/d/'):]
    return Path(value)


def fingerprint(path):
    raw = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def files():
    return sorted([REPORT, *[p for p in HERE.rglob('*') if p.is_file()]],
                  key=lambda p: p.relative_to(ROOT).as_posix())


def inspect():
    package = json.loads((HERE / 'preparation.json').read_text(encoding='utf-8'))
    data = package['data']; summary = data['summary']; rows = data['results']
    replay = json.loads((HERE / 'read-only-reparse-output.json').read_text(encoding='utf-8-sig'))
    assert replay['mode'] == 'read_only_reparse_verification'
    assert all(replay[k] == v for k, v in summary.items())
    assert summary['metric_count'] == 18 and summary['family_count'] == 11
    assert len(rows) == summary['public_parser_calls'] == 268
    assert len(data['raw_artifacts']) == summary['unique_artifact_count'] == 250
    assert summary['scalar_count'] == sum(len(r.get('parsed', {}).get('scalars', [])) for r in rows)
    assert summary['parse_status_counts'] == dict(Counter(r['parse_status'] for r in rows))
    assert len(package['execution']['calls']) == len(rows)
    assert package['execution']['pythonpath_unset'] and package['execution']['bytecode_disabled']
    assert data['code_identity']['python_executable'] == '/home/tywin/.local/share/pring-cycle/dev-venv/bin/python'
    assert not data['code_identity']['editable_install']
    assert all(f['lf_normalized_equal'] for f in data['code_identity']['files'])
    byte_count = 0
    for item in data['raw_artifacts']:
        raw = local_path(item['cas_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['sha256']
        assert len(raw) == item['bytes']
        assert item['acquisition_time'] is None and not item['historical_first_publication_certified']
        byte_count += len(raw)
    assert byte_count == summary['unique_artifact_bytes'] == 20069217
    for item in data['inputs']:
        raw = local_path(item['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['sha256'] and len(raw) == item['bytes']
    scalars = [s for r in rows for s in r.get('parsed', {}).get('scalars', [])]
    scalar_review = dict(Counter(s['independent_review_status'] for s in scalars))
    assert scalar_review.get('representative_anchor_passed', 0) == 18
    assert scalar_review.get('not_individually_fact_audited', 0) == 1840
    assert all(r['certification_state'] == 'not_performed' and r['candidate_adoption_state'] == 'not_performed' for r in rows)
    for key in ['network_requests','database_operations','certifications_created','candidate_models_created','candidate_adoptions']:
        assert summary[key] == 0
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', REPORT.read_text(encoding='utf-8'))
    local_links = []
    for value in links:
        value = value.strip('<>')
        if urlsplit(value).scheme or value.startswith('#'):
            continue
        assert (ROOT / unquote(value.split('#', 1)[0])).resolve().is_file(), value
        local_links.append(value)
    return {'validation': 'passed', 'validation_scope': 'stdlib_hash_counts_links_only_no_application_import',
            'raw_files_verified': 250, 'raw_bytes_verified': byte_count,
            'public_parser_calls_in_saved_execution': len(rows), 'scalar_count': len(scalars),
            'independent_scalar_review_counts': scalar_review,
            'local_links': len(local_links), 'delivery_path_count': len(files()),
            'new_certification_granted': False}


def manifest(inspected):
    return {'schema': 'p1-official-preparation-delivery-v1', 'manifest_self_hash_excluded': True,
            'inspection': inspected, 'files': [fingerprint(p) for p in files() if p != MANIFEST]}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--write-report', action='store_true')
    parsed = args.parse_args()
    if parsed.write_report:
        if not DELIVERY.exists(): DELIVERY.write_text('', encoding='utf-8')
        if not MANIFEST.exists(): MANIFEST.write_text('{}\n', encoding='utf-8')
        DELIVERY.write_text(''.join(p.relative_to(ROOT).as_posix() + '\n' for p in files()), encoding='utf-8', newline='\n')
        MANIFEST.write_text(json.dumps(manifest(inspect()), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    checked = inspect()
    assert len(files()) == 8
    assert DELIVERY.read_text(encoding='utf-8').splitlines() == [p.relative_to(ROOT).as_posix() for p in files()]
    assert json.loads(MANIFEST.read_text(encoding='utf-8')) == manifest(checked)
    print(json.dumps(checked, ensure_ascii=False, indent=2))
    print(json.dumps({'report': fingerprint(REPORT), 'manifest': fingerprint(MANIFEST)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
