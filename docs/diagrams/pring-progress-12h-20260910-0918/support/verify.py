"""Validate only this report's evidence, UI, and exports."""
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

TASK=Path(__file__).resolve().parent
ROOT=TASK.parents[1]
OUT=ROOT/'docs/diagrams'
BASE='pring-progress-12h-20260910-0918'
os.environ['FONTCONFIG_FILE']=str(TASK/'fonts.conf')
d=json.loads((OUT/(BASE+'.gantt.json')).read_text())
assert datetime.fromisoformat(d['snapshot_at'])-datetime.fromisoformat(d['period_start'])==timedelta(hours=12)
for src,v in d['sources'].items():
    raw=(ROOT/v['snapshot']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==v['sha256'],src
    assert len(raw)==v['bytes'],src
    assert (ROOT/src).is_file(),src
ids={x['id'] for x in d['pending']}
assert len(ids)==12
for p in d['pending']:
    assert p['start'] is None and p['end'] is None
    assert set(p['depends'])<=ids
def visit(id,stack):
    assert id not in stack
    for dep in next(p for p in d['pending'] if p['id']==id)['depends']:visit(dep,stack+[id])
for id in ids:visit(id,[])
protected=json.loads((TASK/'protected-before.json').read_text())
for name,h in protected.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
report={'status':'pending','evidence_snapshots':len(d['sources']),'past_tasks':len(d['tasks']),
        'pending_groups':len(ids),'date_window_hours':12,'plan_has_no_invented_dates':True,
        'protected_existing_files':len(protected),'errors':[],'measurements':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/home/tywin/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':1000},device_scale_factor=1)
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.goto((OUT/(BASE+'.html')).as_uri()+'?theme=light')
    page.wait_for_function('window.ganttReady === true')
    page.evaluate('document.fonts.ready')
    for view in ['overview','plan']:
        page.locator('#g-'+view).click()
        for width,height in [(1440,900),(1600,1000),(1920,1080),(2048,1320)]:
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(250)
            dims=page.evaluate('({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight})')
            dims['view']=view
            report['measurements'].append(dims)
            assert dims['scrollWidth']<=width and dims['scrollHeight']<=height,dims
            if (width,height) in [(1440,900),(2048,1320)]:
                page.screenshot(path=str(TASK/f'{view}-{width}-light.png'))
        selector='[data-task]' if view=='overview' else '[data-plan]'
        expected=11 if view=='overview' else 12
        assert page.locator(selector).count()==expected
        for i in range(expected):
            page.locator(selector).nth(i).focus()
            page.keyboard.press('Enter')
            assert page.locator('#g-dialog').is_visible()
            assert page.locator('#g-dialog a').count()>=2
            page.keyboard.press('Escape')
        page.locator('#btn-theme').click()
        assert page.locator('html').get_attribute('data-theme')=='dark'
        page.screenshot(path=str(TASK/f'{view}-2048-dark.png'))
        page.locator('#btn-theme').click()
        suffix='' if view=='overview' else '-pending'
        for fmt in ['svg','png']:
            page.locator('#btn-export').click()
            with page.expect_download() as downloaded:page.locator(f'[data-format="{fmt}"]').click()
            target=TASK/f'native{suffix}.svg' if fmt=='svg' else OUT/(BASE+suffix+'.png')
            if target.exists():
                assert (TASK/'visual-round-0').is_dir(),target
            downloaded.value.save_as(str(target))
    page.locator('#g-overview').click()
    for i in range(4):
        page.locator('[data-stage]').nth(i).click()
        assert page.locator('#g-dialog').is_visible()
        assert page.locator('#g-dialog .g-task').count()>0
        page.locator('#g-close').click()
    for suffix in ['','-pending']:
        page.goto((OUT/(BASE+suffix+'.svg')).as_uri())
        assert page.locator('parsererror').count()==0
    browser.close()
assert not report['errors'],report['errors']
report.update(status='passed',detail_dialogs=27,keyboard_and_pointer='passed',native_svg_and_png_exports='passed',themes='passed',standalone_svgs='passed')
report['artifact_sha256']=hashlib.sha256((OUT/(BASE+'.html')).read_bytes()).hexdigest()
(TASK/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
