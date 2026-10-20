"""Read-only evidence checks and browser QA for this newly generated artifact."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/diagrams'
TASK = ROOT / '.scratch/pring-execution-gantt'
os.environ['FONTCONFIG_FILE'] = str(TASK / 'fonts.conf')
data = json.loads((OUT / 'pring-execution-gantt.gantt.json').read_text())
report = {'source_checks': {}, 'browser_checks': {}, 'page_errors': []}
assert len(data['tasks']) == 33 and len(data['groups']) == 12
assert sum(t['status'] == 'completed' for t in data['tasks']) == 32
for t in data['tasks']:
    assert data['period_start'] <= t['start'] <= t['end'] <= data['snapshot_at'], t['id']
    assert (ROOT / t['source']).is_file(), t['source']
for p in data['pending']:
    assert (ROOT / p['source']).is_file(), p['source']
for source, info in data['sources'].items():
    if info['revision'] == data['head_commit']:
        raw = subprocess.check_output(['git', 'show', f"{info['revision']}:{source}"], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == info['sha256'], source
report['source_checks'] = {'groups': 12, 'tasks': 33, 'completed': 32, 'active': 1,
                           'source_links': 'pass', 'committed_source_hashes': 'pass',
                           'date_bounds': 'pass', 'snapshot_at': data['snapshot_at']}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/home/tywin/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome', args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
    page.goto((OUT / 'pring-execution-gantt.html').as_uri() + '?theme=light')
    page.wait_for_function('window.ganttReady === true')
    page.evaluate('document.fonts.ready')
    assert page.locator('[data-gantt-group]').count() == 12
    assert page.locator('.g-summary').is_visible()
    assert page.locator('.g-provenance').is_visible()
    for g in data['groups']:
        row = page.locator(f'[data-gantt-group="{g["id"]}"]')
        row.focus()
        page.keyboard.press('Enter')
        assert page.locator('#g-dialog').is_visible()
        assert page.locator('#g-dialog .g-task').count() == len(g['task_ids'])
        page.locator('#g-close').click()
    page.locator('#g-recent').click()
    expected = sum(g['end'] >= '2026-09-08T00:00:00+08:00' for g in data['groups'])
    assert page.locator('[data-gantt-group]').count() == expected
    assert page.locator('#g-recent').get_attribute('aria-pressed') == 'true'
    page.screenshot(path=str(TASK / 'recent.png'))
    page.locator('#g-all').click()
    assert page.locator('[data-gantt-group]').count() == 12
    page.locator('[data-gantt-group="audit"] .gt-strong').click()
    assert page.locator('#g-dialog').is_visible()
    page.keyboard.press('Escape')
    assert not page.locator('#g-dialog').is_visible()
    page.locator('#g-open').click()
    assert page.locator('#g-dialog .g-task').count() == 4
    page.screenshot(path=str(TASK / 'pending.png'))
    page.locator('#g-close').click()
    page.locator('#btn-theme').click()
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    page.locator('#btn-theme').click()
    assert page.locator('html').get_attribute('data-theme') == 'light'
    page.locator('#btn-export').click()
    with page.expect_download() as item:
        page.locator('[data-format="svg"]').click()
    item.value.save_as(str(TASK / 'native-export.svg'))
    assert 'gt-row' in (TASK / 'native-export.svg').read_text()
    page.locator('#btn-export').click()
    with page.expect_download() as item:
        page.locator('[data-format="png"]').click()
    item.value.save_as(str(OUT / 'pring-execution-gantt.png'))
    page.wait_for_timeout(500)
    page.screenshot(path=str(TASK / 'final-desktop.png'))
    page.goto((OUT / 'pring-execution-gantt.svg').as_uri())
    assert page.locator('parsererror').count() == 0
    assert page.locator('text').count() > 40
    page.screenshot(path=str(TASK / 'standalone-svg.png'))
    report['browser_checks'] = {'all_12_detail_dialogs': 'pass', 'recent_filter': 'pass',
        'pending_4_items': 'pass', 'keyboard_and_pointer': 'pass', 'theme_toggle': 'pass',
        'native_svg_export': 'pass', 'native_png_export': 'pass', 'standalone_svg': 'pass',
        'summary_and_provenance': 'pass'}
    browser.close()
assert not report['page_errors'], report['page_errors']
report['status'] = 'pass'
(OUT / 'pring-execution-gantt.verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False))
