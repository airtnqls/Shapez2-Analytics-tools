#!/usr/bin/env python3
"""Real public HTTPS verification. No fixtures, routing mocks, or CSP bypass."""
import concurrent.futures,hashlib,json,pathlib,re,requests,time,zipfile,io
from playwright.sync_api import sync_playwright
BASE='https://tmam-web.netlify.app/'
OUT=pathlib.Path('live-audit');OUT.mkdir(exist_ok=True)
checks=[];errors=[];failed=[]
def check(name,ok):
    checks.append({'name':name,'pass':bool(ok)});print(name,bool(ok),flush=True)
    if not ok:raise AssertionError(name)
release=requests.get(BASE+'release.json',timeout=45);release.raise_for_status();version=release.json()
check('public English v105 release marker',version.get('version')=='v105' and version.get('locale')=='en')
manifest=requests.get(BASE+'integrity.json',timeout=45);manifest.raise_for_status();manifest=manifest.json()
def verify_file(pair):
    path,meta=pair;r=requests.get(BASE+path,headers={'Accept-Encoding':'identity'},timeout=90);r.raise_for_status()
    b=r.content
    return {'path':path,'ok':len(b)==meta['bytes'] and hashlib.sha256(b).hexdigest()==meta['sha256'],'bytes':len(b)}
public=[x for x in manifest['files'].items() if x[0] not in {'_headers','.nojekyll','vercel.json','netlify.toml'}]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:verified=list(pool.map(verify_file,public))
check('all published application files match manifest',all(x['ok'] for x in verified))
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True)
    context=b.new_context(viewport={'width':1440,'height':1000})
    p=context.new_page();p.set_default_timeout(20000)
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.on('requestfailed',lambda req:failed.append({'url':req.url,'error':req.failure}))
    response=p.goto(BASE,wait_until='networkidle',timeout=60000)
    check('production HTML without login',response.status==200 and p.locator('#searchForm').count()==1)
    check('English document',p.locator('html').get_attribute('lang')=='en')
    check('no initial heavy worker',p.evaluate('TMAM_WEB.getWorker()===null'))
    p.select_option('#cap','3');p.fill('#pattern','c');p.click('#searchBtn')
    p.wait_for_function('TMAM_WEB.getCurrent()?.value === "486775"',timeout=60000)
    check('live cap3 exact crystal count and 24 shapes',p.evaluate('TMAM_WEB.getCurrent().items.length')==24)
    p.screenshot(path=str(OUT/'live-search.png'),full_page=False)
    current=p.evaluate('TMAM_WEB.getCurrent()');qid=current['query_id']
    p.locator('.shapeSelect').first.click()
    check('real shape detail opens',p.locator('#shapeDialog').is_visible())
    p.click('#research-classify')
    p.wait_for_function('TMAMResearchUI.last()?.classification_status === "COMPLETE"',timeout=60000)
    check('research runs from real hosted family data',p.evaluate('TMAMResearchUI.last().cap')==3)
    p.screenshot(path=str(OUT/'live-research.png'),full_page=False)
    p.click('#shapePlace');p.click('#closeShape');p.click('#navSimulator')
    check('selected shape enters workbench',p.locator('#workbench').is_visible() and len(p.evaluate('TMAMWorkbench.getState().items'))>0)
    p.screenshot(path=str(OUT/'live-workbench.png'),full_page=False)
    p.click('#navSearch')
    check('search preserved after workbench',p.evaluate('TMAM_WEB.getCurrent().query_id')==qid)
    p.select_option('#cap','4');p.click('#searchBtn')
    p.wait_for_function('TMAM_WEB.getCurrent()?.value === "43685004"',timeout=90000)
    check('live cap4 WASM exact count',p.evaluate('TMAM_WEB.getCurrent().items.length')==24)
    for w in [390,320]:
        p.set_viewport_size({'width':w,'height':844})
        check('no horizontal page overflow '+str(w),p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        if w==390:p.screenshot(path=str(OUT/'live-mobile.png'),full_page=False)
    # A fresh page proves the hosted viewer scripts and its normal CSP load.
    viewer=context.new_page();viewer.on('pageerror',lambda e:errors.append(str(e)))
    viewer.goto(BASE+'viewer.html',wait_until='networkidle',timeout=60000)
    check('hosted DAG viewer scripts loaded',viewer.evaluate('typeof TMAM_UI === "object"'))
    check('no browser JavaScript errors',not errors)
    b.close()
report={'status':'PASS','url':BASE,'version':version,'checks':checks,'verified_public_files':verified,'page_errors':errors,'request_failures':failed,'scope':'Actual production HTTPS, normal CSP, Chromium browser, real Worker/WASM and data downloads. No fixtures or network interception.'}
(OUT/'LIVE.json').write_text(json.dumps(report,indent=2));print(json.dumps({'status':'PASS','checks':len(checks),'verified_files':len(verified)}))
