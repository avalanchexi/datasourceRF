"""Verify the bounded BSE browser evidence package; default is read-only stdlib.

--write-manifest refreshes only this package's delivery list and manifest.
It never requests a URL, runs a browser, or imports project application code.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / 'margin-bse-browser-followup.md'
MANIFEST = HERE / 'delivery-verification.json'
DELIVERY = HERE / 'delivery-files.txt'
OFFICIAL_URL = 'https://www.bse.cn/disclosure/rzrq_trans_list.html'
PRIOR = ROOT / 'margin-bse-followup.md'
PRIOR_SHA = '4b6690e908b3a92d71f502e94011f88b2bf634a423dd573cd9ddd9dfe5c58b62'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(path):
    body = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest()}


def paths():
    return sorted([REPORT, *[p for p in HERE.rglob('*') if p.is_file()]],
                  key=lambda p: p.relative_to(ROOT).as_posix())


def inspect():
    prior = fingerprint(PRIOR)
    require(prior['sha256'] == PRIOR_SHA, 'immutable prior BSE report hash mismatch')
    require(prior['bytes'] == 9657, 'immutable prior BSE report length mismatch')
    data = json.loads((HERE / 'browser-actions.json').read_text(encoding='utf-8'))
    text = (HERE / 'browser-tool-record.txt').read_text(encoding='utf-8')
    require(data['record_kind'] == 'agent_transcription_of_tool_observations', 'record identity')
    require(data['target_date'] == '2026-08-28', 'target date changed')
    require(data['official_url'] == OFFICIAL_URL, 'URL must be existing official entry')
    require(data['navigation_limit'] == 2, 'navigation budget changed')
    actions = data['actions']
    require([a['api'] for a in actions] == [
        'cua.getBrowser', 'Browser.nameSession', 'cua.createBrowserTab'], 'unexpected browser action')
    nav = [a for a in actions if a['navigation_attempt']]
    require(len(nav) == 1, 'navigation call denominator mismatch')
    require(nav[0]['url'] == OFFICIAL_URL, 'navigation to an unapproved URL')
    require(nav[0]['timeout_ms'] == 60000 and nav[0]['tool_wall_time_seconds'] == 60.2151,
            'tool timeout/wall-time mismatch')
    require(nav[0]['tool_result'] == 'js execution timed out; kernel reset, rerun your request',
            'tool result mismatch')
    require(nav[0]['tool_result'] in text, 'exact result missing from transcript')
    for action in actions:
        require(action['exact_started_at'] is None and action['exact_completed_at'] is None,
                'unreturned exact timing must stay unknown')
    for key in ['page_url_observed', 'page_title_observed', 'http_status', 'redirect_chain',
                'browser_network_request_count', 'page_read_at', 'dom_artifact',
                'screenshot_artifact', 'official_download_artifact',
                'official_response_body_artifact', 'login_or_captcha_observed']:
        require(nav[0][key] is None, f'unobserved page field became known: {key}')
    require(nav[0]['tab_handle_returned'] is False and nav[0]['partial_tab_creation'] == 'unknown',
            'tab creation or handle claim changed')
    require(nav[0]['block_cause'] == 'tool_timeout_unknown_site_or_transport_cause',
            'tool timeout must not be assigned a site/network cause')
    require(data['post_failure_clock'] == {
        'utc': '2026-09-07T15:16:01Z', 'tool': 'clock.curr_time',
        'purpose': 'post_failure_bookkeeping_only', 'navigation_start_or_end': False,
        'official_data_read_or_publication_time': False}, 'post-failure clock boundary changed')
    expected_counts = {
        'browser_navigation_attempts': 1, 'remaining_navigation_budget_unused': 1,
        'successful_page_state_returns': 0, 'direct_http_get_attempts': 0,
        'browser_http_request_count': None, 'valid_target_date_samples': 0,
        'dom_artifacts': 0, 'screenshots': 0, 'official_downloads': 0,
        'official_raw_bytes': 0, 'tavily_requests': 0, 'exa_requests': 0,
        'source_certifications': 0, 'model_adoptions': 0}
    require(data['counts'] == expected_counts, 'observed counts changed')
    for key in ['access_control_interaction', 'credentials_read_or_used',
                'proxy_or_system_settings_changed', 'other_user_tabs_enumerated']:
        require(data[key] is False, f'out-of-scope interaction: {key}')
    for key in ['official_publication_at', 'public_available_at', 'production_system_available_at']:
        require(data[key] is None, f'unsupported availability time: {key}')
    require('no_handle_returned_partial_creation_unknown' in data['task_tab_cleanup'],
            'unknown tab must not be claimed closed')
    require('not an official page' in text and 'No screenshot' in text,
            'transcript must not masquerade as source bytes')
    report_text = REPORT.read_text(encoding='utf-8')
    local_links = []
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', report_text):
        value = target.strip('<>')
        if urlsplit(value).scheme or value.startswith('#'):
            continue
        local_path = (REPORT.parent / unquote(value.split('#', 1)[0])).resolve()
        require(local_path.is_file(), f'broken report link: {target}')
        local_links.append(target)
    require('有效目标样本 0' in report_text and 'HTTP 请求数未知' in report_text,
            'report missing result/count limitation')
    return {'research_delivery_validation': 'passed', **expected_counts,
            'delivery_path_count': len(paths()), 'report_local_link_count': len(local_links),
            'prior_report': prior, 'default_verification': 'read_only_standard_library',
            'certification_granted': False}


def build_manifest(inspection):
    return {'schema': 'bounded-browser-research-delivery-v1',
            'manifest_self_hash_excluded': True,
            'inspection': inspection,
            'files': [fingerprint(p) for p in paths() if p != MANIFEST]}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args()
    if args.write_manifest:
        # These two named files are the only outputs; all other evidence stays immutable.
        if not MANIFEST.exists():
            MANIFEST.write_text('{}\n', encoding='utf-8', newline='\n')
        if not DELIVERY.exists():
            DELIVERY.write_text('', encoding='utf-8', newline='\n')
        DELIVERY.write_text(''.join(p.relative_to(ROOT).as_posix() + '\n' for p in paths()),
                            encoding='utf-8', newline='\n')
        result = inspect()
        MANIFEST.write_text(json.dumps(build_manifest(result), ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8', newline='\n')
    result = inspect()
    expected_paths = [p.relative_to(ROOT).as_posix() for p in paths()]
    require(DELIVERY.read_text(encoding='utf-8').splitlines() == expected_paths,
            'delivery list does not exactly match current package files plus report')
    require(len(expected_paths) == 6, 'unexpected added or missing delivery file')
    saved = json.loads(MANIFEST.read_text(encoding='utf-8'))
    require(saved == build_manifest(result), 'manifest content/hash mismatch')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('report=' + json.dumps(fingerprint(REPORT), ensure_ascii=False))
    print('manifest=' + json.dumps(fingerprint(MANIFEST), ensure_ascii=False))


if __name__ == '__main__':
    main()
