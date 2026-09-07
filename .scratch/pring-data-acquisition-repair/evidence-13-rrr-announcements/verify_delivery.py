"""Standard-library read-only verification by default. No network, app imports, or DB."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPORT = PROJECT / 'rrr-announcements-followup.md'
OLD_MANIFEST = PROJECT / 'evidence-13-rrr-followup/delivery-verification.json'
OLD_MANIFEST_SHA = '775dd73b38f62382cea2a0b1802f9cf4fe6948485a41ef5a763856742e598a58'
EXPECTED = {
    18: {'sha256': '28a9f4cbde775f247aadcf57cb00bfd61a2d6cf2b143fd89135cb1a74c6287c8', 'bytes': 28544,
         'title': '中国人民银行公告﹝2026﹞第18号', 'topic': '北京中轴线金银纪念币发行',
         'identity_phrase': '北京中轴线金银纪念币一套', 'document_date': '2026-07-16',
         'visible_published_local': '2026-07-22 09:12:23', 'coin_issuance_date': '2026-07-27'},
    20: {'sha256': '94c9c9fa851bd92b46dd7400fe1f629c0dcafb6b3567b19fdb57f704d95bef1f', 'bytes': 23564,
         'title': '中国人民银行公告〔2026〕第20号', 'topic': '授权德意志银行股份有限公司担任法兰克福人民币清算行',
         'identity_phrase': '授权德意志银行股份有限公司担任法兰克福人民币清算行', 'document_date': '2026-08-07',
         'visible_published_local': '2026-08-10 17:05:44', 'coin_issuance_date': None},
    21: {'sha256': '8ae204fb99e40f561274234dae37bc960e409ca523cf21afb58a6d1878ce13f7', 'bytes': 27812,
         'title': '中国人民银行公告﹝2026﹞第21号', 'topic': '江泽民诞辰100周年纪念币发行',
         'identity_phrase': '江泽民诞辰100周年纪念币', 'document_date': '2026-08-14',
         'visible_published_local': '2026-08-14 18:10:08', 'coin_issuance_date': '2026-08-17'},
    22: {'sha256': '08ef3d75785d478189ad533ff82575e8f2770a27df3f6ea950c4757cc2d5ad15', 'bytes': 26903,
         'title': '中国人民银行公告﹝2026﹞第22号', 'topic': '科创未来（人工智能）金银纪念币发行',
         'identity_phrase': '科创未来（人工智能）金银纪念币一套', 'document_date': '2026-08-22',
         'visible_published_local': '2026-08-28 11:00:00', 'coin_issuance_date': '2026-09-04'},
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def dump(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def clean(s):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def inspect():
    assert sha(OLD_MANIFEST.read_bytes()) == OLD_MANIFEST_SHA
    old_manifest = load(OLD_MANIFEST)
    for f in old_manifest['files']:
        raw = (PROJECT / f['path']).read_bytes()
        assert sha(raw) == f['sha256'] and len(raw) == f['bytes'], f['path']
    old = load(PROJECT / 'evidence-13-rrr-followup/source-inspection.json')
    allowed = {r['url']: r for r in old['unread_generic_announcements']}
    receipts = load(ROOT / 'receipts.json')
    assert len(receipts) == 4 and {r['url'] for r in receipts} == set(allowed)
    assert sum(r['bytes'] for r in receipts) == 106823
    rows = []
    for r in receipts:
        assert r['method'] == 'GET' and not r['automatic_redirects']
        assert r['status'] == 200 and not r['truncated'] and r['public_available_at'] is None
        assert r['final_url'] == r['url'] and urlsplit(r['url']).hostname == 'www.pbc.gov.cn'
        assert datetime.fromisoformat(r['started_at']) <= datetime.fromisoformat(r['received_at'])
        raw = (ROOT / r['local_file']).read_bytes()
        assert sha(raw) == r['sha256'] == r['local_file'] and len(raw) == r['bytes']
        s = raw.decode('utf-8')
        title = clean(re.search(r'<title>(.*?)</title>', s, re.S)[1])
        number = int(re.search(r'第(\d+)号', title)[1])
        expected = EXPECTED[number]
        assert expected['title'] == title and expected['sha256'] == r['sha256'] and expected['bytes'] == r['bytes']
        body = re.search(r'<div id="zoom" class="zoom1">(.*?)</div>', s, re.S)[1]
        body_text = clean(body)
        assert expected['identity_phrase'] in body_text
        published = re.search(r'<!--\d{4}年\d{2}月\d{2}日-->(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', s)[1]
        assert published == expected['visible_published_local']
        pubdate = re.search(r'<meta name="PubDate" content="([^"]+)"', s)[1]
        assert pubdate == published[:10] == allowed[r['url']]['listed_date']
        date_matches = re.findall(r'(\d{4})年(\d{1,2})月(\d{1,2})日', body_text)
        dates = [f'{int(y):04}-{int(m):02}-{int(d):02}' for y, m, d in date_matches]
        assert dates[-1] == expected['document_date']
        if expected['coin_issuance_date']:
            assert dates[0] == expected['coin_issuance_date']
        else:
            assert dates == [expected['document_date']]
        terms = {word: body_text.count(word) for word in ['降准', '准备金', '存款准备金率']}
        assert terms == {'降准': 0, '准备金': 0, '存款准备金率': 0}
        raw_list = (PROJECT / 'evidence-13-rrr-followup' / allowed[r['url']]['source_sha256']).read_text(encoding='utf-8')
        assert urlsplit(r['url']).path in raw_list
        attachments = [{'url': urljoin(r['url'], url), 'text': clean(label), 'downloaded': False}
                       for url, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)]
        rows.append({**expected, 'number': number, 'url': r['url'], 'listed_date': allowed[r['url']]['listed_date'],
                     'started_at': r['started_at'], 'received_at': r['received_at'],
                     'source_list_sha256': allowed[r['url']]['source_sha256'],
                     'body_text': body_text, 'body_dates_in_source_order': dates,
                     'body_rrr_keyword_counts': terms, 'rrr_relevance': 'not_an_rrr_policy_notice',
                     'rrr_effective_date': None, 'rrr_change_pp': None, 'rrr_scope': None,
                     'rrr_model_public_available_at': None, 'rrr_new_event_count': 0,
                     'attachment_links_not_requested': attachments})
    return {'network_requests': 4, 'http_2xx': 4, 'http_failures': 0, 'raw_bytes': 106823,
            'valid_article_bodies': 4, 'rrr_event_notices': 0,
            'candidate_body_identity_resolved': 4, 'candidate_rejected_as_non_rrr': 4,
            'search_calls': 0, 'new_directory_reads': 0, 'attachment_downloads': 0,
            'tavily_or_exa_requests': 0, 'database_reads_or_writes': 0, 'certifications_or_model_adoptions': 0,
            'whole_rrr_interval_no_event_proven': False,
            'source_timezone_note': 'No explicit offset in visible HTML clock; Asia/Shanghai remains existing project convention, not new official proof.',
            'old_delivery_paths_verified': old_manifest['delivery_paths'],
            'rows': sorted(rows, key=lambda row: row['number'])}


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
    names = (ROOT / 'delivery-files.txt').read_text(encoding='utf-8').splitlines()
    actual = sorted(['rrr-announcements-followup.md'] + [p.relative_to(PROJECT).as_posix() for p in ROOT.iterdir() if p.is_file()])
    assert names == sorted(set(names)) == actual
    files = []
    for name in names:
        if name == 'evidence-13-rrr-announcements/delivery-verification.json':
            continue
        raw = (PROJECT / name).read_bytes()
        files.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw)})
    result = {'verification': 'passed', 'default_read_only_stdlib': True,
              'new_raw_count': 4, 'new_raw_bytes': 106823,
              'old_rrr_delivery_paths_verified': 20,
              'delivery_paths': len(names), 'report_local_links': len(local_links),
              'manifest_self_hash_excluded': True, 'files': files}
    if args.write_manifest:
        dump(ROOT / 'delivery-verification.json', result)
    else:
        assert result == load(ROOT / 'delivery-verification.json')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
