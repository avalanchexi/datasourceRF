"""Default: read-only, Python standard library, no network/app imports/database.

Explicit --write-inspection/--write-manifest only materialize this new research package.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPORT = PROJECT / 'rrr-policy-status-followup.md'
OLD_MANIFEST = PROJECT / 'evidence-13-rrr-followup/delivery-verification.json'
OLD_MANIFEST_SHA = '775dd73b38f62382cea2a0b1802f9cf4fe6948485a41ef5a763856742e598a58'
SOURCES = [
    {'id': '2026_h1_press_conference',
     'url': 'https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026071518015458230/index.html',
     'title': '国新办举行新闻发布会 介绍2026年上半年货币政策执行和金融统计数据情况',
     'sha256': '1223082d38efc5039ef7febabbeaebecc92853222b0a18d8c0bfa91e8a08d415', 'bytes': 59959,
     'visible_published_local': '2026-07-15 18:49:06', 'source_event_date': '2026-07-15',
     'source_event_time_local': '15:00', 'body_paragraph_count': 79,
     'expected_keyword_counts': {'准备金': 3, '降准': 1, '存款准备金率': 0, '存准': 0},
     'relevant_paragraph_numbers': [7, 21, 58]},
    {'id': '2026_h2_work_meeting',
     'url': 'https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026080209562668921/index.html',
     'title': '中国人民银行召开2026年下半年工作会议',
     'sha256': 'dff58ae83cae68b5839fbeb75c5c8298c16eba1c7901631b2cb347ac36488c52', 'bytes': 34996,
     'visible_published_local': '2026-08-02 15:00:08', 'source_event_date': '2026-08-01',
     'source_event_time_local': None, 'body_paragraph_count': 24,
     'expected_keyword_counts': {'准备金': 0, '降准': 0, '存款准备金率': 0, '存准': 0},
     'relevant_paragraph_numbers': []},
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def clean(html):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', html))).strip()


def inspect():
    assert sha(OLD_MANIFEST.read_bytes()) == OLD_MANIFEST_SHA
    old_manifest = load(OLD_MANIFEST)
    for f in old_manifest['files']:
        raw = (PROJECT / f['path']).read_bytes()
        assert len(raw) == f['bytes'] and sha(raw) == f['sha256'], f['path']
    prior = load(PROJECT / 'evidence-13-rrr-followup/source-inspection.json')
    old_titles = {r['url']: r for r in prior['news_title_entries']}
    receipts = load(ROOT / 'receipts.json')
    assert len(receipts) == 2 and {r['url'] for r in receipts} == {s['url'] for s in SOURCES}
    assert sum(r['bytes'] for r in receipts) == 94955
    rows = []
    for source in SOURCES:
        r = next(r for r in receipts if r['url'] == source['url'])
        assert r['method'] == 'GET' and r['status'] == 200 and not r['truncated']
        assert not r['automatic_redirects'] and r['final_url'] == r['url'] and r['public_available_at'] is None
        assert datetime.fromisoformat(r['started_at']) <= datetime.fromisoformat(r['received_at'])
        assert r['sha256'] == r['local_file'] == source['sha256'] and r['bytes'] == source['bytes']
        raw = (ROOT / source['sha256']).read_bytes()
        assert sha(raw) == source['sha256'] and len(raw) == source['bytes']
        s = raw.decode('utf-8')
        title = clean(re.search(r'<title>(.*?)</title>', s, re.S)[1])
        assert title == source['title'] == old_titles[r['url']]['title']
        body_html = re.search(r'<div id="zoom" class="zoom1">(.*?)</div>', s, re.S)[1]
        body = clean(body_html)
        paragraphs = [clean(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body_html, re.S)]
        assert len(paragraphs) == source['body_paragraph_count']
        counts = {term: body.count(term) for term in source['expected_keyword_counts']}
        assert counts == source['expected_keyword_counts']
        relevant = [i for i, p in enumerate(paragraphs, 1) if any(t in p for t in ['准备金', '降准', '存准'])]
        assert relevant == source['relevant_paragraph_numbers']
        published = re.search(r'<!--\d{4}年\d{2}月\d{2}日-->(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', s)[1]
        assert published == source['visible_published_local']
        pubdate = re.search(r'<meta name="PubDate" content="([^"]+)"', s)[1]
        assert pubdate == published[:10] == old_titles[r['url']]['listed_date']
        raw_list = (PROJECT / 'evidence-13-rrr-followup' / old_titles[r['url']]['source_sha256']).read_text(encoding='utf-8')
        assert urlsplit(r['url']).path in raw_list
        if source['id'] == '2026_h1_press_conference':
            assert '2026年7月15日（星期三）下午3时举行新闻发布会' in paragraphs[0]
            assert '缴纳存款准备金、现金投放等因素带来的1万亿元流动性缺口' in paragraphs[6]
            assert '财政收支、准备金缴存、现金投放等都会有重要影响' in paragraphs[20]
            assert '下半年将如何增强前瞻性灵活性和针对性' in paragraphs[54]
            assert '降准主要侧重于投放长期流动性' in paragraphs[57]
            assert '适当选择并合理搭配这些工具' in paragraphs[57]
            assert '下调结构性货币政策工具利率0.25个百分点' in paragraphs[7]
            focus = sorted(set(relevant + list(range(55, 61))))
            assessment = 'RRR instrument function and liquidity context, no explicit RRR level/change/no-change declaration.'
        else:
            assert paragraphs[:2] == ['', '']
            assert paragraphs[2].startswith('8月1日，中国人民银行召开2026年下半年工作会议。')
            focus = [i for i, p in enumerate(paragraphs, 1) if '货币政策' in p]
            assessment = 'General monetary-policy review and work priorities; RRR omitted, not an explicit no-event declaration.'
        rows.append({**source, 'started_at': r['started_at'], 'received_at': r['received_at'],
                     'source_list_sha256': old_titles[r['url']]['source_sha256'],
                     'body_paragraphs': [{'paragraph': i, 'text': p} for i, p in enumerate(paragraphs, 1)],
                     'nonempty_body_paragraph_count': sum(bool(p) for p in paragraphs),
                     'related_context_paragraphs': [{'paragraph': i, 'text': paragraphs[i-1]} for i in focus],
                     'keyword_counts': counts, 'assessment': assessment,
                     'rrr_current_rate_percent': None, 'rrr_effective_date': None,
                     'rrr_change_pp': None, 'rrr_scope': None,
                     'explicit_rrr_no_change_declaration': False,
                     'rrr_model_public_available_at': None, 'rrr_model_usable_event_count': 0})
    return {'network_requests': 2, 'http_2xx': 2, 'http_failures': 0, 'raw_count': 2, 'raw_bytes': 94955,
            'valid_official_article_count': 2, 'rrr_semantic_context_documents': 1,
            'rrr_event_or_current_rate_documents': 0, 'explicit_rrr_no_change_documents': 0,
            'rrr_model_usable_event_count': 0, 'event_census_established': False,
            'search_calls': 0, 'new_directory_requests': 0, 'attachment_requests': 0,
            'tavily_or_exa_requests': 0, 'database_reads_or_writes': 0,
            'certification_or_model_adoption_count': 0, 'old_delivery_paths_verified': 20,
            'timezone_note': 'Source HTML visible clocks have no explicit offset. Asia/Shanghai is an existing project convention, not newly proven here.',
            'semantic_review_limit': 'Keyword counts are reproducible but are not, alone, a proof of semantic absence. Assessments rely on manual reading of all preserved body paragraphs.',
            'rows': rows}


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
        print(json.dumps({k: v for k, v in inspection.items() if k != 'rows'}, ensure_ascii=False))
        return
    local_links = []
    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', REPORT.read_text(encoding='utf-8')):
        if urlsplit(link).scheme or link.startswith('#'):
            continue
        target = (PROJECT / link.split('#', 1)[0]).resolve()
        assert target.is_relative_to(PROJECT) and target.exists(), link
        local_links.append(link)
    paths = (ROOT / 'delivery-files.txt').read_text(encoding='utf-8').splitlines()
    actual = sorted(['rrr-policy-status-followup.md'] + [p.relative_to(PROJECT).as_posix() for p in ROOT.iterdir() if p.is_file()])
    assert paths == sorted(set(paths)) == actual
    files = []
    for path in paths:
        if path == 'evidence-13-rrr-policy-status/delivery-verification.json':
            continue
        raw = (PROJECT / path).read_bytes()
        files.append({'path': path, 'bytes': len(raw), 'sha256': sha(raw)})
    result = {'verification': 'passed', 'default_read_only_stdlib': True,
              'new_raw_count': 2, 'new_raw_bytes': 94955,
              'old_rrr_delivery_paths_verified': 20,
              'delivery_paths': len(paths), 'report_local_links': len(local_links),
              'manifest_self_hash_excluded': True, 'files': files}
    if args.write_manifest:
        dump(ROOT / 'delivery-verification.json', result)
    else:
        assert result == load(ROOT / 'delivery-verification.json')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
