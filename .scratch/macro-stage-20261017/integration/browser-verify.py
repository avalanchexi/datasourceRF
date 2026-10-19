"""只读验收：唯一网络来源 127.0.0.1:8072；仅点击抽屉及区间切换。"""
from pathlib import Path
from urllib.parse import urlparse
import json, sys, os
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / 'shots'
SHOTS.mkdir(exist_ok=True)
BASE = 'http://127.0.0.1:8072/'
SECTIONS = {'01': 'conclusion', '04': 'confirmation', '06': 'history'}
# Chromium 临时配置和缓存均限制在当前工作目录。
os.environ['TMPDIR'] = str(ROOT / 'browser-tmp')
Path(os.environ['TMPDIR']).mkdir(exist_ok=True)


def capture():
    evidence = {'cases': [], 'errors': [], 'blocked': [], 'clicks': [], 'requests': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width':1440,'height':1000}, device_scale_factor=1)
        def restrict(route):
            u = urlparse(route.request.url)
            if u.scheme == 'http' and u.netloc == '127.0.0.1:8072':
                evidence['requests'].append({'method':route.request.method,'url':route.request.url})
                route.continue_()
            else:
                evidence['blocked'].append(route.request.url)
                route.abort()
        context.route('**/*', restrict)
        page = context.new_page()
        page.on('console', lambda m: evidence['errors'].append({'type':'console error','text':m.text}) if m.type=='error' else None)
        page.on('pageerror', lambda e: evidence['errors'].append({'type':'pageerror','text':str(e)}))
        def ready():
            page.locator('#conclusion').get_by_text('宏观判断：第五阶段',exact=False).wait_for(timeout=60000)
            page.wait_for_function("document.querySelector('#history .js-plotly-plot')?.data?.length > 0",timeout=60000)
            page.wait_for_timeout(500)
        def click(selector):
            element = page.locator(selector)
            permitted = element.evaluate("e => e.matches('.drawer-trigger,.drawer-close,.history-view,#theme-toggle')")
            assert permitted, selector
            evidence['clicks'].append({'selector':selector,'text':element.inner_text()})
            element.click()
            page.wait_for_timeout(200)
        def shot(name, selector=None):
            path = str(SHOTS / (name+'.png'))
            if selector:
                page.locator(selector).screenshot(path=path, animations='disabled', timeout=15000)
            else:
                page.screenshot(path=path, animations='disabled', timeout=15000)
        def close_drawer(id):
            click('#'+id+' .drawer-close')
            page.locator('#'+id).wait_for(state='hidden')
        def open_drawer(id):
            click('a.drawer-trigger[aria-controls="'+id+'"]')
            page.locator('#'+id).wait_for(state='visible')
        page.goto(BASE, wait_until='domcontentloaded')
        ready()
        evidence['page_text'] = page.locator('body').inner_text()
        evidence['sections'] = {n:page.locator('#'+id).inner_text() for n,id in SECTIONS.items()}
        evidence['cards'] = page.locator('#confirmation .dimension-grid > *').all_inner_texts()
        evidence['terms'] = page.evaluate('''() => {
          const terms=['正式阶段','暂无正式阶段','确认度不适用','（不计数）'];
          const result={};
          for(const term of terms){
            const nodes=[]; const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
            while(walker.nextNode()){
              const n=walker.currentNode, e=n.parentElement;
              if(e.closest('script,style') || !n.textContent.includes(term))continue;
              const txt=n.textContent;
              nodes.push({count:txt.split(term).length-1,text:txt.length>600?txt.slice(Math.max(0,txt.indexOf(term)-90),txt.indexOf(term)+200):txt,
                location:e.closest('[role=dialog]')?.id || e.closest('section')?.id || e.tagName,
                visible:!!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden'});
            }
            result[term]={visible:(document.body.innerText.split(term).length-1),dom:nodes.reduce((a,n)=>a+n.count,0),nodes};
          } return result;
        }''')
        evidence['chart'] = page.locator('#history .js-plotly-plot').evaluate('''e => ({data:e.data.map(t=>({type:t.type,x:t.x,y:t.y,z:t.z,text:t.text,hovertemplate:t.hovertemplate,colorscale:t.colorscale,zmin:t.zmin,zmax:t.zmax})),layout:{yaxis:e.layout.yaxis,xaxis:e.layout.xaxis}})''')
        for theme in ['light','dark']:
            for width in [1440,908,390]:
                print(f'采集 {theme}/{width}',file=sys.stderr,flush=True)
                page.set_viewport_size({'width':width,'height':1000})
                page.evaluate('(theme)=>localStorage.setItem("pring-cycle-theme",theme)',theme)
                page.goto(BASE,wait_until='domcontentloaded')
                ready()
                # 显式 reload，让主题从 localStorage 初始化。
                page.reload(wait_until='domcontentloaded')
                ready()
                case={'theme':theme,'width':width}
                case['metrics']=page.evaluate('''() => ({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,
                  theme:document.documentElement.getAttribute('data-theme'), heights:Object.fromEntries(['conclusion','confirmation','history'].map(id=>[id,document.getElementById(id).getBoundingClientRect().height]))})''')
                case['overflow_elements']=page.evaluate('''()=>[...document.querySelectorAll('body *')].filter(e=>e.getClientRects().length && e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,id:e.id,cls:typeof e.className==='string'?e.className:'',right:e.getBoundingClientRect().right,text:(e.innerText||'').slice(0,100)})).slice(0,40)''')
                page.screenshot(path=str(SHOTS/f'full-{theme}-{width}.png'),full_page=True,animations='disabled',timeout=20000)
                for num,id in SECTIONS.items():
                    shot(f'{num}-{theme}-{width}','#'+id)
                shot(f'07-{theme}-{width}','#reading')
                open_drawer('drawer-conclusion-price-verification')
                drawer=page.locator('#drawer-conclusion-price-verification')
                case['drawer']={'text':drawer.inner_text(),'rect':drawer.bounding_box(),'sizes':drawer.evaluate('e=>({clientWidth:e.clientWidth,scrollWidth:e.scrollWidth,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight})')}
                shot(f'01-drawer-{theme}-{width}')
                close_drawer('drawer-conclusion-price-verification')
                case['closed']={'hidden':not drawer.is_visible(),'dialogs':page.locator('[role=dialog]:visible').count(),'focus':page.evaluate('document.activeElement?.outerHTML.slice(0,500)'),'scrollWidth':page.evaluate('document.documentElement.scrollWidth')}
                case['history_before']={'text':page.locator('#history').inner_text(),'pressed':page.locator('.history-view').evaluate_all('es=>es.map(e=>({text:e.innerText,pressed:e.getAttribute("aria-pressed")}))')}
                click('.history-view[data-history-view="macro"]')
                case['history_after']={'text':page.locator('#history').inner_text(),'pressed':page.locator('.history-view').evaluate_all('es=>es.map(e=>({text:e.innerText,pressed:e.getAttribute("aria-pressed")}))')}
                shot(f'06-macro-{theme}-{width}','#history')
                if theme=='light' and width==1440:
                    open_drawer('drawer-history-macro-interval-2026-10-14')
                    evidence['macro_interval']=page.locator('#drawer-history-macro-interval-2026-10-14').inner_text()
                    shot('06-macro-detail-light-1440')
                    close_drawer('drawer-history-macro-interval-2026-10-14')
                    open_drawer('drawer-history-macro-interval-2026-04-21')
                    shot('06-macro-old-light-1440')
                    close_drawer('drawer-history-macro-interval-2026-04-21')
                    click('.history-view[data-history-view="official"]')
                    open_drawer('drawer-history-interval-2026-08-04')
                    evidence['price_interval']=page.locator('#drawer-history-interval-2026-08-04').inner_text()
                    page.locator('#drawer-history-interval-2026-08-04 .record-row').last.scroll_into_view_if_needed()
                    shot('06-price-detail-light-1440')
                    close_drawer('drawer-history-interval-2026-08-04')
                    open_drawer('drawer-history-interval-2026-04-21')
                    shot('06-price-old-light-1440')
                    close_drawer('drawer-history-interval-2026-04-21')
                    open_drawer('drawer-history-calendar')
                    evidence['calendar_last']=page.locator('#drawer-history-calendar tbody tr').all_inner_texts()[-5:]
                    page.locator('#drawer-history-calendar tbody tr').last.scroll_into_view_if_needed()
                    shot('06-calendar-light-1440')
                    close_drawer('drawer-history-calendar')
                    open_drawer('drawer-assets-attribution')
                    evidence['attribution']=page.locator('#drawer-assets-attribution').inner_text()
                    shot('02-attribution-light-1440')
                    close_drawer('drawer-assets-attribution')
                    open_drawer('drawer-reading-report')
                    shot('07-report-light-1440')
                    close_drawer('drawer-reading-report')
                # 恢复默认价格区间，避免后续样本受状态影响。
                if page.locator('.history-view[data-history-view="official"]').get_attribute('aria-pressed')!='true':
                    click('.history-view[data-history-view="official"]')
                evidence['cases'].append(case)
                (ROOT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
        evidence['page_alerts']=page.locator('[role=alert],.dash-error-card,.dash-error-container').all_inner_texts()
        browser.close()
    (ROOT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    return evidence


def report(e):
    from report_builder import build
    text=build(e)
    (ROOT/'report.txt').write_text(text)
    print(text)


def followup():
    e=json.loads((ROOT/'evidence.json').read_text())
    e['anchor_checks']=[]
    from PIL import Image
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':908,'height':1000})
        context.route('**/*',lambda r:r.continue_() if urlparse(r.request.url).netloc=='127.0.0.1:8072' and urlparse(r.request.url).scheme=='http' else r.abort())
        page=context.new_page()
        page.on('console',lambda m:e['errors'].append({'type':'console error','text':m.text}) if m.type=='error' else None)
        page.goto(BASE,wait_until='domcontentloaded')
        page.locator('#conclusion .macro-title').wait_for(timeout=60000)
        page.wait_for_function("document.querySelector('#history .js-plotly-plot')?.data?.length>0",timeout=60000)
        page.evaluate("localStorage.setItem('pring-cycle-theme','light')")
        page.reload(wait_until='domcontentloaded')
        page.locator('#conclusion .macro-title').wait_for(timeout=60000)
        page.wait_for_function("document.querySelector('#history .js-plotly-plot')?.data?.length>0",timeout=60000)
        for theme in ['light','dark']:
            if page.locator('html').get_attribute('data-theme')!=theme:
                page.locator('#theme-toggle').click()
                e['clicks'].append({'selector':'#theme-toggle','text':'切换明暗主题'})
            for width in [908,390]:
                print(f'复核锚点 {theme}/{width}',file=sys.stderr,flush=True)
                page.set_viewport_size({'width':width,'height':1000})
                anchor=page.locator('a[href$="#confirmation"]').first
                anchor.click()
                e['clicks'].append({'selector':'a[href$="#confirmation"]','text':anchor.inner_text()})
                page.wait_for_timeout(500)
                ck={'theme':theme,'width':width,'rect':page.locator('#confirmation').bounding_box(),'focus':page.evaluate('document.activeElement?.outerHTML.slice(0,500)')}
                page.screenshot(path=str(SHOTS/f'04-anchor-{theme}-{width}.png'))
                # 用顶部整页截图截取原始坐标，避免 locator 自动滚动带入悬浮导航。
                page.evaluate('window.scrollTo(0,0)')
                page.wait_for_timeout(300)
                boxes={n:page.locator('#'+id).bounding_box() for n,id in SECTIONS.items()}
                page.screenshot(path=str(SHOTS/f'full-{theme}-{width}.png'),full_page=True)
                with Image.open(SHOTS/f'full-{theme}-{width}.png') as im:
                    for n,b in boxes.items():
                        original=SHOTS/f'{n}-{theme}-{width}.png'
                        if original.exists() and not (SHOTS/f'{n}-scroll-{theme}-{width}.png').exists(): original.rename(SHOTS/f'{n}-scroll-{theme}-{width}.png')
                        im.crop((round(b['x']),round(b['y']),round(b['x']+b['width']),round(b['y']+b['height']))).save(original)
                e['anchor_checks'].append(ck)
        page.set_viewport_size({'width':1440,'height':1000})
        page.locator('#theme-toggle').click()
        page.locator('#history').scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        plot=page.locator('#history .js-plotly-plot')
        coords=plot.evaluate('''el=>{const r=el.getBoundingClientRect(),l=el._fullLayout;return {x:r.x+l.xaxis._offset,y:r.y+l.yaxis._offset,w:l.xaxis._length,h:l.yaxis._length}}''')
        e['hover']=[]
        for i,date in enumerate(['2026-10-14','2026-10-15','2026-10-16','2026-10-19']):
            page.mouse.move(coords['x']+coords['w']*(116+i+0.5)/120,coords['y']+coords['h']/10)
            page.wait_for_timeout(200)
            e['hover'].append({'date':date,'text':plot.locator('.hoverlayer').text_content()})
        page.screenshot(path=str(SHOTS/'06-hover-light-1440.png'))
        browser.close()
    (ROOT/'evidence.json').write_text(json.dumps(e,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if '--follow-up' in sys.argv:
        followup()
    elif '--report-only' in sys.argv:
        report(json.loads((ROOT/'evidence.json').read_text()))
    else:
        capture()
        followup()
        report(json.loads((ROOT/'evidence.json').read_text()))
