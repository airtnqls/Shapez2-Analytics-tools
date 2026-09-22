#!/usr/bin/env python3
"""Deploy the verified release using a one-use, runner-only encrypted handoff.
Only the public key and ciphertext are committed. The private key and temporary
Netlify proxy URL stay in this process; neither is logged or uploaded.
"""
import base64, hashlib, io, json, os, pathlib, sys, time, urllib.parse, zipfile
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SITE='f0f9cc84-52ab-4bd0-9f39-0c10c8573886'
REPO='airtnqls/Shapez2-Analytics-tools'
TAG='tmam-v105-ready-20260923'
RUN=os.environ['GITHUB_RUN_ID']; BRANCH=os.environ['GITHUB_REF_NAME']
assert BRANCH=='deploy/tmam-client-v105'
API='https://api.github.com/repos/'+REPO
headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'TMAM-authorized-deployer'}
session=requests.Session()

def api(method,path,**kwargs):
    r=session.request(method,API+path,headers=headers,timeout=45,**kwargs)
    if r.status_code>=400:raise RuntimeError('GitHub API HTTP '+str(r.status_code))
    return r.json()

def put(path,obj):
    api('PUT','/contents/'+path,json={'branch':BRANCH,'message':'deploy(tmam): record '+path.rsplit('/',1)[-1],'content':base64.b64encode(json.dumps(obj,indent=2).encode()).decode()})

def read(path):
    r=session.get(API+'/contents/'+path,headers=headers,params={'ref':BRANCH},timeout=45)
    if r.status_code==404:return None
    if r.status_code!=200:raise RuntimeError('GitHub read HTTP '+str(r.status_code))
    return json.loads(base64.b64decode(r.json()['content']))

def main():
    release=api('GET','/releases/tags/'+TAG)
    assets={a['name']:a for a in release['assets']}
    assert {'tmam-v105-static-en.zip','release-verification.json'} <= assets.keys()
    def get_asset(name):
        u=assets[name]['browser_download_url']
        assert u.startswith('https://github.com/'+REPO+'/releases/download/'+TAG+'/')
        r=requests.get(u,timeout=(30,180));r.raise_for_status();return r.content
    record=json.loads(get_asset('release-verification.json'))
    assert record['version']=='v105' and record['locale']=='en' and record['files']==66
    source=get_asset('tmam-v105-static-en.zip')
    assert len(source)==record['bytes'] and hashlib.sha256(source).hexdigest()==record['sha256']
    source_zip=zipfile.ZipFile(io.BytesIO(source))
    assert len(source_zip.namelist())==66
    integrity=json.loads(source_zip.read('integrity.json'))
    for name,meta in integrity['files'].items():
        b=source_zip.read(name)
        assert len(b)==meta['bytes'] and hashlib.sha256(b).hexdigest()==meta['sha256'],name
    # Netlify builds this already-built static source without adding a server.
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in source_zip.namelist():
            p=pathlib.PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts
            z.writestr(name,source_zip.read(name))
        z.writestr('netlify.toml','[build]\n  command = "echo Verified TMAM static release"\n  publish = "."\n[build.processing]\n  skip_processing = true\n')
    package=out.getvalue()
    key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
    pem=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    challenge=base64.b64encode(os.urandom(24)).decode()
    aad=('TMAM-v105:'+RUN+':'+SITE+':'+challenge).encode()
    request={'schema':'tmam.deploy.handoff.v1','run_id':RUN,'site_id':SITE,'public_key':pem,'challenge':challenge,'created_at':int(time.time()),'expires_at':int(time.time())+900,'release_sha256':record['sha256']}
    put('tmam-client/handshake/request-'+RUN+'.json',request)
    print('Verified release ready; waiting for the authorized encrypted handoff.',flush=True)
    deadline=time.monotonic()+900
    reply=None
    while time.monotonic()<deadline:
        reply=read('tmam-client/handshake/response-'+RUN+'.json')
        if reply is not None:break
        time.sleep(5)
    if reply is None:raise RuntimeError('Handoff deadline reached; no deployment attempted')
    assert reply['schema']==request['schema'] and reply['run_id']==RUN and reply['site_id']==SITE
    assert reply['challenge']==challenge
    secret=key.decrypt(base64.b64decode(reply['wrapped_key'],validate=True),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=b'tmam-netlify'))
    plaintext=AESGCM(secret).decrypt(base64.b64decode(reply['nonce'],validate=True),base64.b64decode(reply['ciphertext'],validate=True),aad)
    message=json.loads(plaintext);proxy=message['proxy_url'].rstrip('/')
    parsed=urllib.parse.urlparse(proxy)
    assert parsed.scheme=='https' and parsed.hostname=='netlify-mcp.netlify.app' and parsed.path.startswith('/proxy/')
    assert parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment
    assert message['site_id']==SITE and len(proxy)<10000
    # Mask before any authenticated network call. Never serialize the proxy.
    print('::add-mask::'+proxy,flush=True)
    print('::add-mask::'+parsed.path.removeprefix('/proxy/'),flush=True)
    print('Uploading verified static files to the existing authorized site.',flush=True)
    upload=proxy+'/api/v1/sites/'+SITE+'/builds'
    try:
        r=requests.post(upload,files={'zip':('tmam-v105.zip',package,'application/zip')},headers={'User-Agent':'netlify-mcp'},timeout=(30,300),allow_redirects=False)
    except requests.RequestException:
        raise RuntimeError('Netlify upload network error') from None
    if r.status_code not in (200,201,202):raise RuntimeError('Netlify upload HTTP '+str(r.status_code))
    data=r.json();data=data[0] if isinstance(data,list) else data
    deploy_id=data.get('deploy_id');assert deploy_id,'Missing deploy ID'
    result={'version':'v105','locale':'en','site_id':SITE,'deploy_id':deploy_id,'build_id':data.get('id'),'source_sha256':record['sha256'],'files':66,'run_id':RUN,'state':'submitted'}
    pathlib.Path('deployment-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    end=time.monotonic()+900;last=None
    while time.monotonic()<end:
        try:
            r=requests.get(proxy+'/api/v1/deploys/'+deploy_id,headers={'User-Agent':'netlify-mcp'},timeout=30,allow_redirects=False)
            if r.status_code!=200:time.sleep(5);continue
            d=r.json()
        except (requests.RequestException,ValueError):time.sleep(5);continue
        state=d.get('state')
        if state!=last:print('Netlify deployment state: '+str(state),flush=True);last=state
        if state in ('ready','error','rejected'):
            result.update(state=state,url=d.get('ssl_url') or d.get('url'),published_at=d.get('published_at'),context=d.get('context'))
            break
        time.sleep(5)
    else:result['state']='verification_timeout'
    pathlib.Path('deployment-result.json').write_text(json.dumps(result,indent=2))
    put('tmam-client/deployments/'+RUN+'.json',result)
    print(json.dumps(result),flush=True)
    if result['state']!='ready':raise RuntimeError('Deployment not ready')

if __name__=='__main__':
    try:main()
    except Exception as e:
        # Do not put exception URLs or credential-bearing response bodies in logs.
        allowed=str(e) if isinstance(e,(AssertionError,RuntimeError)) else type(e).__name__
        if 'http' in allowed.lower() and '://' in allowed:allowed=type(e).__name__
        print('Deployment stopped: '+allowed,flush=True)
        sys.exit(1)
