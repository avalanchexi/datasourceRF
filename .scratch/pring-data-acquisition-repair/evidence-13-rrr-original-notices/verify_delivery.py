"""Read-only default verification; standard library, no network/application/database."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPORT = PROJECT / 'rrr-original-notices-followup.md'
CSRC = 'd9dd4873a3005ca20a2985a36055f8b3a14f6d0b67977186351857cc4a011846'
JILIN = 'f1d24e69b5ef8bb4526534fa5cd32f0728a8ff0903b3ff5381d1acb03c06bf83'
OLD = '7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5'
URLS = {
    JILIN: ('https://jr.jl.gov.cn/jrzx/zyjrxxzz/gj/202505/t20250512_3454788.html', 24186),
    CSRC: ('https://www.csrc.gov.cn/csrc/c106311/c7555758/content.shtml', 100491),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def clean(html):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', html))).strip()


def inspect():
    old_raw = (PROJECT / 'evidence-13' / OLD).read_bytes()
    assert sha(old_raw) == OLD and len(old_raw) == 31945
    receipts = load(ROOT / 'receipts.json')
    assert len(receipts) == 2 and {r['sha256'] for r in receipts} == set(URLS)
    assert sum(r['bytes'] for r in receipts) == 124677
    for r in receipts:
        url, size = URLS[r['sha256']]
        assert r['url'] == r['final_url'] == url and r['bytes'] == size
        assert r['method'] == 'GET' and r['status'] == 200 and not r['truncated']
        assert not r['automatic_redirects'] and r['public_available_at'] is None
        assert datetime.fromisoformat(r['started_at']) <= datetime.fromisoformat(r['received_at'])
        raw = (ROOT / r['local_file']).read_bytes()
        assert r['local_file'] == r['sha256'] == sha(raw) and len(raw) == size
    csrc = (ROOT / CSRC).read_text(encoding='utf-8')
    jilin = (ROOT / JILIN).read_text(encoding='utf-8')
    csrc_body = re.search(r'<div class="detail-news">(.*?)</div>', csrc, re.S)[1]
    jilin_body = re.search(r'<div class="trs_editor_view TRS_UEDITOR trs_paper_default trs_web">(.*?)</div>', jilin, re.S)[1]
    csrc_paras = [clean(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', csrc_body, re.S)]
    jilin_paras = [clean(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', jilin_body, re.S)]
    csrc_text, jilin_text = clean(csrc_body), clean(jilin_body)
    c = re.sub(r'\s+', '', csrc_text)
    j = re.sub(r'\s+', '', jilin_text)
    csrc_date = re.search(r'日期：(\d{4}-\d{2}-\d{2})', csrc)[1]
    jilin_posted = re.search(r'日期：(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', jilin)[1]
    assert csrc_date == '2025-05-07' and jilin_posted == '2025-05-12 09:22:58'
    meta_date = re.search(r'<meta name="PubDate" content="([^"]+)"', csrc)[1]
    generated = re.search(r'<meta name="others" content="页面生成时间 ([^"]+)"', csrc)[1]
    assert meta_date == generated == '2026-08-01 21:47:01'
    discovery = load(ROOT / 'web-discovery.json')
    assert discovery['search_calls'] == 2 and discovery['queries'] == 7
    assert sum(len(q) for q in discovery['query_groups']) == 7
    absent_clocks = {clock: csrc.count(clock) for clock in discovery['csrc_search_view_clock_markers_observed']}
    assert not any(absent_clocks.values())
    assert not re.findall(r'2025-05-07\s+\d{2}:\d{2}:\d{2}', clean(csrc))
    assert '第一，降低存款准备金率0.5个百分点' in c
    assert '阶段性将汽车金融公司、金融租赁公司的存款准备金率从目前的5%调降为0%' in c
    assert '阶段性降低汽车金融公司、金融租赁公司的存款准备金率，从目前的5%降至0%' in c
    assert '5月15日' not in c
    assert '自2025年5月15日起，下调金融机构存款准备金率0.5个百分点（不含已执行5％存款准备金率的金融机构），下调汽车金融公司和金融租赁公司存款准备金率5个百分点' in j
    assert 'var laiyuan = "中国人民银行";' in jilin
    assert Decimal('0') - Decimal('5') == Decimal('-5')
    relevant = [{'paragraph': i, 'text': p} for i, p in enumerate(csrc_paras, 1)
                if '存款准备金' in p or '降准' in p]
    assert len(relevant) == 6
    boundaries = load(ROOT / 'source-boundaries.json')
    assert not boundaries['app_imported_or_executed']
    assert '"中国人民银行", "www.pbc.gov.cn", ("CN_RRR_EVENT",)' in boundaries['rrr_descriptor']
    assert 'parsed.hostname != host' in boundaries['url_validation_function']
    check = boundaries['public_boundary_observation']
    assert check['public_parser'] and check['database_writes'] == 0
    result = {r['period']: r for r in check['results']}
    assert result['2026-05']['status'] == 'rejected'
    assert result['2026-05']['error'] == 'official_context_period_identity_mismatch'
    assert len(result['2025-05']['scalars']) == 1
    assert result['2025-05']['scalars'][0]['value'] == -0.5
    return {
        'network_requests': 2, 'get_cap': 4, 'http_2xx': 2, 'http_failures': 0, 'raw_bytes': 124677,
        'search_calls': 2, 'search_queries': 7, 'valid_official_documents': 2,
        'original_pbc_host_notice_downloaded': False,
        'new_certifications': 0, 'model_adoptions': 0, 'new_model_usable_rrr_inputs': 0,
        'effective_date_supported_by_republication_and_old_pbc_chronicle': '2025-05-15',
        'csrc': {
            'url': URLS[CSRC][0], 'sha256': CSRC, 'bytes': 100491,
            'official_host_role': 'CSRC official host of original joint press-conference transcript',
            'visible_date': csrc_date, 'date_precision': 'day', 'original_exact_clock': None,
            'date_only_conservative_boundary_candidate': '2025-05-08T00:00:00+08:00',
            'candidate_boundary_is_source_certification': False,
            'meta_PubDate': meta_date, 'meta_page_generation_time': generated,
            'search_clocks_absent_from_actual_raw': absent_clocks,
            'body_paragraph_count': len(csrc_paras), 'relevant_rrr_paragraphs': relevant,
            'effective_date_in_this_transcript': None,
        },
        'jilin': {
            'url': URLS[JILIN][0], 'sha256': JILIN, 'bytes': 24186,
            'official_host_role': 'Jilin financial authority republication attributed to PBC; not the original PBC site',
            'visible_republication_timestamp_local': jilin_posted,
            'original_pbc_publication_timestamp': None, 'body_paragraphs': jilin_paras,
        },
        'scoped_facts': [
            {'scope': 'financial institutions excluding institutions already at 5%', 'change_pp': -0.5,
             'uniform_post_rate_percent': None, 'weighted_average_post_rate_percent': None,
             'effective_date': '2025-05-15', 'scope_and_effective_date_source': JILIN,
             'change_source': CSRC, 'released_funds_context': 'approximately 1 trillion yuan estimate for broad cut; not an exact institutional allocation'},
            {'scope_members': ['auto finance companies', 'financial leasing companies'],
             'change_pp': -5.0, 'pre_rate_percent': 5.0, 'post_rate_percent': 0.0,
             'post_rate_is_explicit_not_inferred': True, 'source': CSRC,
             'stage_limited': True, 'stage_end_date': None, 'renewal_or_expiry_notice': None,
             'effective_date': '2025-05-15', 'effective_date_source': JILIN,
             'canonical_scope_codes_frozen': False},
        ],
        'acceptance_boundaries': {
            'new_hosts_match_existing_pbc_rrr_notice': False,
            'source_url_may_be_rewritten_to_pbc': False,
            'period_2026_05_public_parser_rejected_in_root_probe': True,
            'local_regex_trial_is_public_bug_reproduction': False,
            'latest_predecessor_as_of_2026_03_09_proven': False,
            'event_census_2026_03_09_to_08_28_proven': False,
            'stage_policy_remained_active_at_replay_start_proven': False,
        },
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-inspection', action='store_true')
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args()
    inspection = inspect()
    if args.write_inspection:
        dump(ROOT / 'source-inspection.json', inspection)
    else:
        assert inspection == load(ROOT / 'source-inspection.json')
    if not REPORT.exists():
        assert args.write_inspection and not args.write_manifest
        print(json.dumps(inspection, ensure_ascii=False, indent=2))
        return
    links = []
    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', REPORT.read_text(encoding='utf-8')):
        if urlsplit(link).scheme or link.startswith('#'):
            continue
        target = (PROJECT / link.split('#', 1)[0]).resolve()
        assert target.is_relative_to(PROJECT) and target.exists(), link
        links.append(link)
    paths = (ROOT / 'delivery-files.txt').read_text(encoding='utf-8').splitlines()
    actual = sorted(['rrr-original-notices-followup.md'] + [p.relative_to(PROJECT).as_posix() for p in ROOT.iterdir() if p.is_file()])
    assert paths == sorted(set(paths)) == actual
    files = []
    for path in paths:
        if path == 'evidence-13-rrr-original-notices/delivery-verification.json':
            continue
        raw = (PROJECT / path).read_bytes()
        files.append({'path': path, 'bytes': len(raw), 'sha256': sha(raw)})
    result = {'verification': 'passed', 'default_read_only_stdlib': True,
              'new_raw_count': 2, 'new_raw_bytes': 124677, 'old_pbc_raw_verified': 1,
              'delivery_paths': len(paths), 'report_local_links': len(links),
              'manifest_self_hash_excluded': True, 'files': files}
    if args.write_manifest:
        dump(ROOT / 'delivery-verification.json', result)
    else:
        assert result == load(ROOT / 'delivery-verification.json')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
