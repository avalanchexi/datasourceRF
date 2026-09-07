"""Read-only by default. Standard library only; no network, application imports or DB.

--write-inspection and --write-manifest explicitly materialize this research delivery.
PDF text is an independently extracted, hash-bound derivative, not re-parsed by stdlib.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPORT = PROJECT / 'rrr-followup.md'
OLD = '7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5'
H1 = 'd8d6c21c65be39471a7ff075bc09b3de85eac3a97dfb4f94785834776167404f'
Q2 = 'b20eba89a6549be9d746b936f59594adc45bd2e94c25eac8552ca5c8b142bf8a'
PDF = '07f1f13795c95d9d842993abd1d83ed8c8726aa59ec48da03208d30cc6dd309c'
LISTS = [
    '91d014730e6553d4ce14b22b23204d906c5474d3916d4ab5d3fa58995878040d',
    '580e0aa3241ab862f07ff7e67f9ca1b33aa6343699a3e0367cfc0804cec6b702',
    '451ce1150b5599b4f3a4ad5c0ac0544b6f147a84f1a519f1b45317c87a44cdf0',
]
OLD_FILES = {
    'research-13.md': (31765, 'dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1'),
    'evidence-13/' + OLD: (31945, OLD),
    'evidence-13/legacy-read-matrix.json': (463940, '740f094e922ae40ddc21098f86629df8ffcaf416c8dc4595def22f93ba5c8b46'),
    'evidence-13/history-verification.json': (1622488, '65a153a43ee952ff40640f5faa86c83539f832d1075fbb652b5dc539c656d977'),
    'evidence-13/imports.json': (5145, '07da00c64b09c728052b2c2ab5ff7156df6e403714f28653e86d4b9c9855b875'),
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(html):
    html = re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>', '', html, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', html))).strip()


def body(html):
    match = re.search(r'<div id="zoom" class="zoom1">(.*?)</div>', html, re.S)
    assert match, 'Missing actual article body'
    return match.group(1)


def posted(html):
    match = re.search(r'<!--\d{4}年\d{2}月\d{2}日-->(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', html)
    assert match, 'Missing visible article timestamp'
    return match.group(1)


def inspect():
    for path, (size, digest) in OLD_FILES.items():
        raw = (PROJECT / path).read_bytes()
        assert (len(raw), sha(raw)) == (size, digest), path
    receipts = load(ROOT / 'receipts.json')
    assert len(receipts) == 6 and len({r['url'] for r in receipts}) == 6
    by_sha = {}
    for r in receipts:
        assert r['method'] == 'GET' and not r['automatic_redirects']
        assert urlsplit(r['url']).hostname == 'www.pbc.gov.cn'
        assert r['status'] == 200 and r['public_available_at'] is None and not r['truncated']
        assert datetime.fromisoformat(r['started_at']) <= datetime.fromisoformat(r['received_at'])
        raw = (ROOT / r['local_file']).read_bytes()
        assert len(raw) == r['bytes'] and sha(raw) == r['sha256'] == r['local_file']
        by_sha[r['sha256']] = r
    assert sum(r['bytes'] for r in receipts) == 4058270
    assert (ROOT / PDF).read_bytes().startswith(b'%PDF-')
    h1 = (ROOT / H1).read_text(encoding='utf-8')
    q2 = (ROOT / Q2).read_text(encoding='utf-8')
    old = (PROJECT / 'evidence-13' / OLD).read_text(encoding='utf-8')
    h1_paragraphs = [text(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body(h1), re.S)]
    events = []
    for p in h1_paragraphs:
        m = re.match(r'(\d{1,2})月(\d{1,2})日', p)
        assert m, p
        events.append({'date': date(2026, int(m[1]), int(m[2])).isoformat(), 'text': p})
    assert not any('降准' in p or '准备金' in p for p in h1_paragraphs)
    assert events[-1]['date'] == '2026-07-04'
    titles = []
    for i, digest in enumerate(LISTS, 1):
        html = (ROOT / digest).read_text(encoding='utf-8')
        matches = re.findall(r'<a href="([^"]+)"[^>]*title="([^"]+)" istitle="true">.*?</a></font><span class="hui12">(\d{4}-\d{2}-\d{2})</span>', html)
        assert len(matches) == 15
        titles.extend({'list_page': i, 'source_sha256': digest, 'url': urljoin(by_sha[digest]['url'], url), 'title': unescape(title), 'listed_date': day} for url, title, day in matches)
    assert len({t['url'] for t in titles}) == 45
    assert min(t['listed_date'] for t in titles) == '2026-06-30'
    assert max(t['listed_date'] for t in titles) == '2026-09-04'
    assert sum('2026-07-01' <= t['listed_date'] <= '2026-08-28' for t in titles) == 40
    generic = [t for t in titles if re.fullmatch(r'中国人民银行公告.*第\d+号', t['title'])]
    assert len(generic) == 4
    assert all(t['url'] not in {r['url'] for r in receipts} for t in generic)
    # Every new GET follows a raw preserved link, except the initial entry linked by old raw.
    assert '/goutongjiaoliu/113456/113469/index.html' in old
    for i in (1, 2, 3, 4, 5):
        r = receipts[i]
        relative = urlsplit(r['url']).path
        previous = ''.join((ROOT / z['local_file']).read_text(encoding='utf-8') for z in receipts[:i] if z['sha256'] != PDF)
        assert relative in previous, ('No earlier official link evidence', relative)
    pdf_text = load(ROOT / 'q2-report-text.json')
    assert pdf_text['source_sha256'] == PDF
    pages = pdf_text['pages']
    extracted = '\n'.join(p['text'] for p in pages)
    poppler = (ROOT / 'q2-report-poppler.txt').read_text(encoding='utf-8')
    keyword_counts = {}
    for term in ['降准', '准备金', '存款准备金率', '超额准备金率']:
        a, b = extracted.count(term), poppler.count(term)
        assert a == b, (term, a, b)
        keyword_counts[term] = a
    assert keyword_counts['降准'] == 0 and keyword_counts['存款准备金率'] == 0
    assert '金融机构超额准备金率为1.3%' in re.sub(r'\s+', '', extracted)
    old_rrr = next(p for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body(old), re.S) if '5月15日' in text(p) and '存款准备金率' in text(p))
    old_rrr = text(old_rrr)
    assert '0.5个百分点' in old_rrr and '不含已执行5%' in old_rrr
    assert '汽车金融公司和金融租赁公司存款准备金率5个百分点' in old_rrr
    matrix = load(PROJECT / 'evidence-13/legacy-read-matrix.json')
    legacy = next(row for row in matrix['metrics'] if row['metric_id'] == 'CN_RRR_EVENT')
    sample = legacy['legacy_queries']['public_at_target']['latest_sample']
    assert len(sample) == 1 and sample[0]['selected_value'] == -0.5 and sample[0]['period_start'] == '2025-05-15'
    assert legacy['legacy_queries']['system_at_target']['point_count'] == 0
    history = load(PROJECT / 'evidence-13/history-verification.json')
    assert 'pbc_rrr_notice' not in history['families'] and history['raw_record_count'] == 270
    prior = load(ROOT / 'prior-attempts.json')
    imported = next(r for r in load(PROJECT / 'evidence-13/imports.json') if r['sha256'] == OLD)
    assert imported['imported_at'] == prior['existing_evidence_imported_at']
    previous_urls = {r['url'] for r in load(PROJECT / 'evidence-13/receipts.json')}
    assert not previous_urls.intersection(r['url'] for r in receipts)
    # Observed legacy algorithm, copied for evidence. This is NOT the desired behavior.
    pattern = (r'(?P<month>\d{1,2})月(?P<day>\d{1,2})日[^。；]{0,80}'
               r'下调金融机构存款准备金率\s*(?P<change>\d+(?:\.\d+)?)\s*个百分点'
               r'(?P<scope>[^。；]*)')
    matches = re.findall(pattern, text(body(old)))
    matches = [m for m in matches if int(m[0]) == 5]
    assert len(matches) == 1
    wrong_year_date = date(2026, int(matches[0][0]), int(matches[0][1])).isoformat()
    assert wrong_year_date == '2026-05-15'
    return {
        'network_requests': 6, 'http_2xx': 6, 'http_failed': 0,
        'response_bytes': 4058270, 'new_rrr_event_rows_proven': 0,
        'new_certifications': 0, 'model_adoptions': 0, 'database_reads_or_writes': 0,
        'old_raw_sha256': OLD, 'old_raw_bytes': 31945,
        'combined_primary_raw_bytes': 4090215,
        'old_rrr_article_visible_timestamp': posted(old),
        'old_rrr_paragraph': old_rrr,
        'old_known_event_components': [
            {'effective_date': '2025-05-15', 'change_pp': -0.5, 'scope': 'financial institutions excluding those already at 5%', 'original_announcement_at': None, 'post_rate': None},
            {'effective_date': '2025-05-15', 'change_pp': -5.0, 'scope': 'auto finance and financial leasing companies', 'original_announcement_at': None, 'post_rate': None},
        ],
        'legacy_rrr_public_points_at_target': 1, 'legacy_rrr_system_points_at_target': 0,
        'legacy_history_270_contains_rrr': False,
        'h1_visible_timestamp': posted(h1), 'q2_html_visible_timestamp': posted(q2),
        'timezone_note': 'Visible page timestamps have no offset; Asia/Shanghai is existing project source convention, not newly proved by these raw pages.',
        'h1_entries': events, 'h1_entry_count': len(events), 'h1_rrr_entry_count': 0,
        'h1_claimed_period': ['2026-01-01', '2026-06-30'],
        'h1_last_listed_event_date': events[-1]['date'],
        'news_title_entries': titles, 'news_title_count': len(titles),
        'news_titles_in_2026_07_01_to_08_28': 40,
        'unread_generic_announcements': generic,
        'pdf_page_count': len(pages), 'pdf_keyword_counts_two_extractors_agree': keyword_counts,
        'pdf_reserve_keyword_pages': [p['pdf_page'] for p in pages if '准备金' in p['text']],
        'pdf_text_verification_limit': 'Default stdlib validates source hash and both stored extraction derivatives; it does not independently decode PDF text.',
        'legacy_regex_wrong_year_counterexample': {'raw_article_year': 2025, 'requested_period': '2026-05', 'observed_fallback_effective_date': wrong_year_date, 'required_result': 'reject year mismatch; never create this 2026 event'},
        'coverage_result': 'no RRR event listed in reviewed H1 chronology; interval event completeness unknown, not proven no-event',
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
        print(json.dumps({k: v for k, v in inspection.items() if k not in ['h1_entries', 'news_title_entries']}, ensure_ascii=False, indent=2))
        return
    links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', REPORT.read_text(encoding='utf-8'))
    local_links = []
    for link in links:
        if urlsplit(link).scheme or link.startswith('#'):
            continue
        p = (PROJECT / unquote(link.split('#', 1)[0])).resolve()
        assert p.is_relative_to(PROJECT) and p.exists(), link
        local_links.append(link)
    names = (ROOT / 'delivery-files.txt').read_text(encoding='utf-8').splitlines()
    assert names == sorted(set(names))
    actual = sorted([REPORT.relative_to(PROJECT).as_posix()] + [p.relative_to(PROJECT).as_posix() for p in ROOT.iterdir() if p.is_file()])
    assert names == actual, ('Delivery list differs from actual files', names, actual)
    files = []
    for name in names:
        if name == 'evidence-13-rrr-followup/delivery-verification.json':
            continue
        raw = (PROJECT / name).read_bytes()
        files.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw)})
    manifest = {'verification': 'passed', 'mode': 'stdlib read-only by default', 'new_gets': 6,
                'new_raw_bytes': 4058270, 'new_raw_count': 6, 'reused_raw_count': 1,
                'local_report_links': len(local_links), 'delivery_paths': len(names),
                'manifest_self_hash_excluded': True, 'files': files}
    if args.write_manifest:
        dump(ROOT / 'delivery-verification.json', manifest)
    else:
        assert manifest == load(ROOT / 'delivery-verification.json')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
