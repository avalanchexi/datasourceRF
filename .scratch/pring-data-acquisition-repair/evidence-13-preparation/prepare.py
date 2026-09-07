"""A18 existing-byte public-parser preparation. Default reparses and verifies read-only.

Run only the specified installed WSL Python with env -u PYTHONPATH and -B.
--write-report writes this package's preparation.json; no other application API is called.
"""
import argparse
import calendar
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
CAS = Path('/home/tywin/.local/share/pring-cycle/artifacts/sha256')
PYTHON = '/home/tywin/.local/share/pring-cycle/dev-venv/bin/python'
MANIFEST = ROOT / 'evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec'
OLD = ROOT / 'evidence-13/history-verification.json'
OUTPUT = HERE / 'preparation.json'


def fingerprint(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalized(v) for v in value]
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?[+]\d\d:\d\d', value):
        return datetime.fromisoformat(value).isoformat()
    return value


class PageText(HTMLParser):
    """Independent visible-text/meta collector, not the application's parser."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.meta = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {'style', 'script'}:
            self.skip += 1
        if tag == 'meta' and str(values.get('name', '')).lower() in {'pubdate', 'createdate', 'articletitle'}:
            self.meta.append(values)

    def handle_endtag(self, tag):
        if tag in {'style', 'script'}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def page_evidence(raw):
    page = PageText()
    page.feed(raw.decode('utf-8-sig'))
    text = re.sub(r'\s+', ' ', ' '.join(page.parts))
    pattern = r'\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d\d(?::\d\d)?'
    matches = [{'text': m.group(), 'context': text[max(0, m.start()-60):m.end()+60]}
               for m in re.finditer(pattern, text)]
    return {'metadata': page.meta, 'visible_datetime_occurrences': matches,
            'visible_text_sha256': hashlib.sha256(text.encode()).hexdigest()}, text


def period_binding(scalar, requested):
    kind = scalar['period_kind']
    year = int(requested[:4])
    if kind == 'business_day':
        expected = (requested, requested)
    elif kind in {'month', 'year_to_month'} and re.fullmatch(r'\d{4}-\d{2}', requested):
        month = int(requested[-2:])
        expected = (f'{year}-01-01' if kind == 'year_to_month' else f'{requested}-01',
                    f'{requested}-{calendar.monthrange(year, month)[1]:02d}')
    elif kind in {'quarter', 'year_to_quarter'} and re.fullmatch(r'\d{4}-Q[1-4]', requested):
        quarter = int(requested[-1]); month = quarter * 3
        expected = (f'{year}-01-01' if kind == 'year_to_quarter' else f'{year}-{month-2:02d}-01',
                    f'{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}')
    else:
        return 'not_independently_checked_for_this_period_kind'
    return 'calendar_binding_matches' if (scalar['period_start'], scalar['period_end']) == expected else 'needs_review'


def parser_identity(module):
    installed = Path(module.__file__).resolve().parent
    assert 'site-packages/pring_cycle' in str(installed)
    files = []
    for source in sorted((REPO / 'src/pring_cycle').rglob('*.py')):
        relative = source.relative_to(REPO / 'src/pring_cycle')
        target = installed / relative
        source_bytes = source.read_bytes()
        installed_bytes = target.read_bytes()
        equal = source_bytes.replace(b'\r\n', b'\n') == installed_bytes.replace(b'\r\n', b'\n')
        files.append({'relative_path': relative.as_posix(),
                      'workspace_sha256': hashlib.sha256(source_bytes).hexdigest(),
                      'installed_sha256': hashlib.sha256(installed_bytes).hexdigest(),
                      'lf_normalized_equal': equal})
    assert all(v['lf_normalized_equal'] for v in files), 'installed/workspace source mismatch'
    return {'public_callable': 'pring_cycle.official_context.parse_official_context_document',
            'module_file': str(Path(module.__file__).resolve()),
            'python_executable': sys.executable, 'python_version': sys.version,
            'files': files, 'files_checked': len(files),
            'editable_install': False,
            'editable_basis': 'module resolved to the specified dev-venv site-packages, and package direct_url editable flag checked'}


def execute():
    assert sys.platform == 'linux' and sys.executable == PYTHON, 'use the exact required WSL Python'
    assert 'PYTHONPATH' not in os.environ and sys.dont_write_bytecode
    assert os.getuid() != 0 and os.environ.get('USER') == 'tywin'
    import pring_cycle.official_context as official
    distribution = importlib.metadata.distribution('pring-cycle')
    direct = distribution.read_text('direct_url.json')
    assert not (json.loads(direct or '{}').get('dir_info', {}).get('editable', False))
    code = parser_identity(official)
    started = datetime.now(UTC)
    monotonic = time.monotonic()
    # This timestamp only satisfies the public pure-parser argument; it is not acquisition evidence.
    parse_clock = started
    history = json.loads(MANIFEST.read_text())
    old = json.loads(OLD.read_text())
    old_by_key = {(r['artifact_hash'], r['family']): r for r in old['results']}
    expected = json.loads((HERE / 'anchor-expectations.json').read_text())['anchors']
    metric_ids = {a['metric_id'] for a in expected}
    families = {a['family'] for a in expected}
    readiness = (ROOT / 'p1-certification-readiness.md').read_text()
    ready_ids = {re.search(r'`(CN_[A-Z0-9_]+)`', line).group(1)
                 for line in readiness.splitlines() if re.match(r'^\| \d{2} `CN_', line) and '**A**' in line}
    assert metric_ids == ready_ids and len(metric_ids) == 18 and len(families) == 11
    records = []
    events = []
    raw_checks = []
    visible = {}
    for record in history['records']:
        selected = sorted(set(record['families']) & families)
        if record.get('lpr') or not selected:
            continue
        sha = record['artifact_hash']
        path = CAS / sha[:2] / sha
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == sha
        page, text = page_evidence(raw)
        visible[sha] = text
        raw_checks.append({'sha256': sha, 'bytes': len(raw), 'cas_path': str(path),
                           'source_url': record['source_url'], 'requested_period': record['period'],
                           'page_evidence': page, 'original_transport_receipt_in_this_package': False,
                           'acquisition_time': None, 'historical_first_publication_certified': False})
        for family in selected:
            call_started = datetime.now(UTC)
            item = {'artifact_sha256': sha, 'source_url': record['source_url'],
                    'family': family, 'expected_period': record['period'],
                    'legacy_manifest_release_at_reference_only': record['release_at'],
                    'certification_state': 'not_performed', 'candidate_adoption_state': 'not_performed'}
            try:
                parsed = official.parse_official_context_document(
                    raw, family=family, source_url=record['source_url'],
                    expected_period=record['period'], fetched_at=parse_clock)
                value = normalized(asdict(parsed))
                assert {s['metric_id'] for s in value['scalars']} <= metric_ids
                identity_keys = [(s['metric_id'], s['source_field'], s['period_kind'],
                                  s['period_start'], s['period_end'], json.dumps(s['dimensions'], sort_keys=True))
                                 for s in value['scalars']]
                prior = old_by_key.get((sha, family))
                release = value['release_at']
                visible_times = [p['text'].replace('/', '-') for p in page['visible_datetime_occurrences']]
                release_text = datetime.fromisoformat(release).strftime('%Y-%m-%d %H:%M:%S') if release else None
                matching = [v for v in visible_times if release_text and v in {release_text, release_text[:16]}]
                item.update({'parse_status': 'parsed_current_public_interface', 'parsed': value,
                             'scalar_count': len(value['scalars']),
                             'duplicate_scalar_identity_count': len(identity_keys)-len(set(identity_keys)),
                             'old_result_comparison': ('equal_after_datetime_serialization_normalization'
                                 if prior and value == normalized(prior.get('parsed')) else 'different_or_missing'),
                             'page_time_review': {'matching_visible_datetime': matching,
                                 'status': 'visible_datetime_matches_parser' if matching else 'needs_independent_page_time_review',
                                 'matched_precision': sorted({'second' if len(v) == 19 else 'minute' for v in matching}),
                                 'timezone_basis': 'project_Asia_Shanghai_interpretation_not_new_timezone_certification',
                                 'scope': 'lexical_match_only_not_first_publication_or_revision_authentication'}})
            except Exception as error:
                item.update({'parse_status': 'parse_failed', 'error_type': type(error).__name__, 'error': str(error)})
            events.append({'artifact_sha256': sha, 'family': family, 'started_at': call_started.isoformat(),
                           'completed_at': datetime.now(UTC).isoformat(), 'result': item['parse_status']})
            records.append(item)
    anchors = []
    for expectation in expected:
        matches = [(r, s) for r in records if r['family'] == expectation['family']
                   and r['expected_period'] == expectation['period'] and 'parsed' in r
                   for s in r['parsed']['scalars'] if s['metric_id'] == expectation['metric_id']
                   and s['dimensions'] == expectation['dimensions']]
        passing = [(r, s) for r, s in matches if Decimal(str(s['value'])) == Decimal(expectation['value'])
                   and s['unit'] == expectation['unit'] and s['source_field'] == expectation['source_field']]
        anchors.append({'expectation': expectation, 'matching_candidates': len(matches),
                        'status': 'representative_anchor_passed' if len(passing) == 1 and len(matches) == 1 else 'needs_review',
                        'source_artifacts': [r['artifact_sha256'] for r, _s in matches],
                        'independence_scope': 'one_explicit_source_based_expectation_per_metric_not_all_historical_scalars'})
    for r in records:
        for s in r.get('parsed', {}).get('scalars', []):
            s['independent_period_binding_status'] = period_binding(s, r['expected_period'])
            s['field_unit_dimension_shape_status'] = ('nonempty_field_unit_and_string_dimensions'
                if isinstance(s['source_field'], str) and s['source_field']
                and isinstance(s['unit'], str) and s['unit']
                and isinstance(s['dimensions'], dict)
                and all(isinstance(k, str) and isinstance(v, str) for k, v in s['dimensions'].items())
                else 'needs_review')
            s['independent_review_status'] = ('representative_anchor_passed' if any(
                a['status'] == 'representative_anchor_passed' and a['expectation']['metric_id'] == s['metric_id']
                and a['expectation']['period'] == r['expected_period']
                and a['expectation']['dimensions'] == s['dimensions'] for a in anchors)
                else 'not_individually_fact_audited')
    family_summary = {}
    for family in sorted(families):
        group = [r for r in records if r['family'] == family]
        family_summary[family] = {'parse_calls': len(group), 'unique_artifacts': len({r['artifact_sha256'] for r in group}),
            'periods': len({r['expected_period'] for r in group}),
            'first_period': min(r['expected_period'] for r in group), 'last_period': max(r['expected_period'] for r in group),
            'scalar_count': sum(r.get('scalar_count', 0) for r in group),
            'parse_status_counts': dict(Counter(r['parse_status'] for r in group))}
    metric_summary = {}
    for metric in sorted(metric_ids):
        scalars = [(r, s) for r in records for s in r.get('parsed', {}).get('scalars', []) if s['metric_id'] == metric]
        metric_summary[metric] = {'scalar_count': len(scalars),
            'period_count': len({r['expected_period'] for r, _s in scalars}),
            'units': sorted({s['unit'] for _r, s in scalars}),
            'source_fields': sorted({s['source_field'] for _r, s in scalars}),
            'period_kinds': sorted({s['period_kind'] for _r, s in scalars}),
            'by_period': dict(sorted(Counter(r['expected_period'] for r, _s in scalars).items())),
            'certification_state': 'not_performed', 'historical_public_state': 'not_certified',
            'candidate_adoption_state': 'not_performed'}
    special = []
    for family, period, metric, count, absent, token in [
        ('nbs_core_cpi','2026-01','CN_CPI_HEADLINE',2,'cumulative_average_yoy','同比涨跌幅'),
        ('nbs_core_cpi','2026-01','CN_CORE_CPI',2,'cumulative_average_yoy','环比涨跌幅'),
        ('nbs_ppi','2026-01','CN_PPI',6,'cumulative_average_yoy','同比涨跌幅'),
        ('nbs_industrial_value_added','2026-02','CN_INDUSTRIAL_VA',2,'current_month_real_yoy','1—2月份'),
        ('pbc_omo_notice','2026-08-11','CN_OMO_7D_RATE',0,None,'操作量为零')]:
        row = next(r for r in records if r['family'] == family and r['expected_period'] == period)
        ss = [s for s in row.get('parsed', {}).get('scalars', []) if s['metric_id'] == metric]
        compact = re.sub(r'\s+', '', visible[row['artifact_sha256']])
        status = len(ss) == count and (not absent or all(s['dimensions'].get('measure') != absent for s in ss)) and token in compact
        special.append({'family': family, 'period': period, 'metric_id': metric,
                        'artifact_sha256': row['artifact_sha256'], 'source_url': row['source_url'],
                        'expected_scalar_count': count, 'observed_scalar_count': len(ss),
                        'absent_measure_not_to_fabricate': absent, 'independent_visible_token': token,
                        'token_present': token in compact, 'status': 'passed' if status else 'needs_review'})
    summary = {'preparation_state': 'parsed_materials_only_not_certification', 'metric_count': len(metric_ids),
               'family_count': len(families), 'unique_artifact_count': len(raw_checks),
               'unique_artifact_bytes': sum(r['bytes'] for r in raw_checks), 'public_parser_calls': len(records),
               'parse_status_counts': dict(Counter(r['parse_status'] for r in records)),
               'scalar_count': sum(r.get('scalar_count', 0) for r in records),
               'scalar_period_binding_counts': dict(Counter(s['independent_period_binding_status']
                   for r in records for s in r.get('parsed', {}).get('scalars', []))),
               'anchor_status_counts': dict(Counter(a['status'] for a in anchors)),
               'old_comparison_counts': dict(Counter(r.get('old_result_comparison','no_current_result') for r in records)),
               'page_time_status_counts': dict(Counter(r.get('page_time_review',{}).get('status','no_current_result') for r in records)),
               'special_case_status_counts': dict(Counter(r['status'] for r in special)),
               'network_requests': 0, 'database_operations': 0, 'certifications_created': 0,
               'candidate_models_created': 0, 'candidate_adoptions': 0}
    return {'schema': 'p1-official-preparation-v1',
            'execution': {'started_at': started.isoformat(), 'completed_at': datetime.now(UTC).isoformat(),
                'elapsed_seconds': time.monotonic()-monotonic, 'user': os.environ.get('USER'),
                'pythonpath_unset': 'PYTHONPATH' not in os.environ, 'bytecode_disabled': bool(sys.dont_write_bytecode),
                'parser_fetched_at_argument': parse_clock.isoformat(),
                'parser_fetched_at_meaning': 'research_validation_clock_not_acquisition_or_historical_publication',
                'calls': events},
            'data': {'summary': summary, 'code_identity': code, 'inputs': [fingerprint(MANIFEST), fingerprint(OLD),
                fingerprint(ROOT / 'p1-certification-readiness.md'), fingerprint(HERE / 'anchor-expectations.json')],
                'raw_artifacts': raw_checks, 'family_summary': family_summary, 'metric_summary': metric_summary,
                'anchor_checks': anchors, 'special_cases': special, 'results': records}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    result = execute()
    if args.write_report:
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    else:
        saved = json.loads(OUTPUT.read_text())
        assert saved['data'] == result['data'], 'fresh parser/inputs/code differ from saved preparation'
    print(json.dumps({'mode': 'write_new_report' if args.write_report else 'read_only_reparse_verification',
                      **result['data']['summary'], 'elapsed_seconds': result['execution']['elapsed_seconds']},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
