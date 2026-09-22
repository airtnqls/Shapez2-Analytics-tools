#!/usr/bin/env python3
"""Read-only HTTPS audit against the exact audited release, with real Chromium."""
import concurrent.futures, hashlib, io, json, pathlib, traceback, zipfile, requests
from playwright.sync_api import sync_playwright
BASE='https://tmam-web.netlify.app/'
OUT=pathlib.Path('live-audit');OUT.mkdir(exist_ok=True)
report={'url':BASE,'scope':'Actual public HTTPS and Chromium with normal CSP, real downloads, no routing mocks or bypass.','checks':[],'page_errors':[],'console_errors':[],'request_failures':[]}
def save(): (OUT/'LIVE.json').write_text(json.dumps(report,indent=2))
def check(name,ok):
    report['checks'].append({'name':name,'pass':bool(ok)});save();print(name,bool(ok),flush=True)
    if not ok:raise AssertionError(name)
def fetch(path):
    r=requests.get(BASE+path,headers={'Accept-Encoding':'identity'},timeout=(30,120));r.raise_for_status();return r
source=requests.get('https://github.com/airtnqls/Shapez2-Analytics-tools/releases/download/tmam-v105-ready-20260923/tmam-v105-static-en.zip',timeout=(30,180)).content
assert hashlib.sha256(source).hexdigest()=='6c5b33eab4c18fcd231cf797a51cc5da23148318306d2d234a721928d54601fa'
z=zipfile.ZipFile(io.BytesIO(source));manifest=json.loads(z.read('integrity.json'))
release=fetch('release.json').json();report['release']=release
check('public English v105 release marker',release.get('version')=='v105' and release.get('locale')=='en')
public=[(n,m) for n,m in manifest['files'].items() if n not in {'_headers','.nojekyll','vercel.json','netlify.toml'}]
def verify(pair):
    name,meta=pair
    try:
        r=fetch(name);data=r.content;actual=hashlib.sha256(data).hexdigest();ok=actual==meta['sha256'] and len(data)==meta['bytes']
        info={'path':name,'ok':ok,'expected_bytes':meta['bytes'],'actual_bytes':len(data),'expected_sha256':meta['sha256'],'actual_sha256':actual,'content_type':r.headers.get('Content-Type'),'content_encoding':r.headers.get('Content-Encoding'),'final_url':r.url,'csp':r.headers.get('Content-Security-Policy')}
        if not ok and name.endswith(('.html','.js','.json','.css')):
            import difflib
            (OUT/('mismatch-'+name.replace('/','_')+'.diff')).write_text('\n'.join(difflib.unified_diff(z.read(name).decode().splitlines(),data.decode().splitlines(),fromfile='expected/'+name,tofile='public/'+name)))
        return info
    except Exception as e:return {'path':name,'ok':False,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:report['public_files']=list(pool.map(verify,public))
report['byte_mismatches']=[x for x in report['public_files'] if not x['ok']];save()
print('BYTE_MISMATCHES',json.dumps(report['byte_mismatches']),flush=True)
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True)
    context=b.new_context(viewport={'width':1440,'height':1000})
    p=context.new_page();p.set_default_timeout(20000)
    def attach(page):
        page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
        page.on('console',lambda msg:report['console_errors'].append(msg.text) if msg.type=='error' else None)
        page.on('requestfailed',lambda req:report['request_failures'].append({'url':req.url,'error':req.failure}))
    attach(p)
    try:
        response=p.goto(BASE,wait_until='networkidle',timeout=60000)
        p.screenshot(path=str(OUT/'live-initial.png'))
        check('production HTML without login',response.status==200 and p.locator('#searchForm').count()==1)
        check('English document',p.locator('html').get_attribute('lang')=='en')
        check('client application initialized',p.evaluate('typeof TMAM_WEB === "object"'))
        check('no initial heavy worker',p.evaluate('TMAM_WEB.getWorker()===null'))
        p.select_option('#cap','3');p.fill('#pattern','c');p.click('#searchBtn')
        p.wait_for_function('TMAM_WEB.getCurrent()?.value === "486775"',timeout=60000)
        check('live cap3 count and 24 shapes',p.evaluate('TMAM_WEB.getCurrent().items.length')==24)
        p.screenshot(path=str(OUT/'live-search.png'))
        current=p.evaluate('TMAM_WEB.getCurrent()');qid=current['query_id'];report['cap3_result']=current
        p.locator('.shapeSelect').first.click()
        check('real shape detail opens',p.locator('#shapeDialog').is_visible())
        p.click('#research-classify')
        p.wait_for_function('TMAMResearchUI.last()?.classification_status === "COMPLETE"',timeout=60000)
        check('research runs from hosted family data',p.evaluate('TMAMResearchUI.last().cap')==3)
        report['research_result']=p.evaluate('TMAMResearchUI.last()');p.screenshot(path=str(OUT/'live-research.png'))
        p.click('#shapePlace');p.click('#closeShape');p.click('#navSimulator')
        check('shape enters workbench',p.locator('#workbench').is_visible() and len(p.evaluate('TMAMWorkbench.getState().items'))>0)
        p.screenshot(path=str(OUT/'live-workbench.png'))
        p.click('#navSearch');check('search preserved',p.evaluate('TMAM_WEB.getCurrent().query_id')==qid)
        p.select_option('#cap','4');p.click('#searchBtn')
        p.wait_for_function('TMAM_WEB.getCurrent()?.value === "43685004"',timeout=90000)
        check('live cap4 WASM exact count',p.evaluate('TMAM_WEB.getCurrent().items.length')==24)
        report['cap4_result']=p.evaluate('TMAM_WEB.getCurrent()')
        for w in (390,320):
            p.set_viewport_size({'width':w,'height':844})
            check('no horizontal overflow '+str(w),p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            if w==390:p.screenshot(path=str(OUT/'live-mobile.png'))
        viewer=context.new_page();attach(viewer)
        viewer.goto(BASE+'viewer.html',wait_until='networkidle',timeout=60000)
        check('hosted DAG viewer loaded',viewer.evaluate('typeof TMAM_UI === "object"'))
        viewer.screenshot(path=str(OUT/'live-viewer.png'))
        check('no browser JavaScript errors',not report['page_errors'])
        report['browser_status']='PASS'
    except Exception as e:
        report['browser_status']='FAIL';report['browser_error']=str(e)
        report['traceback']=traceback.format_exc()
        try:
            p.screenshot(path=str(OUT/'live-failure.png'));(OUT/'failure-body.txt').write_text(p.locator('body').inner_text())
        except Exception:pass
    finally:
        save();b.close()
report['status']='PASS' if report.get('browser_status')=='PASS' and not report['byte_mismatches'] else 'REVIEW_REQUIRED'
save();print(json.dumps({'status':report['status'],'browser':report.get('browser_status'),'mismatches':len(report['byte_mismatches']),'checks':len(report['checks']),'page_errors':report['page_errors'],'console_errors':report['console_errors'],'browser_error':report.get('browser_error')}),flush=True)
if report['status']!='PASS':raise SystemExit(1)
