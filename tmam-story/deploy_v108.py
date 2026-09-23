#!/usr/bin/env python3
"""Publish an already verified TMAM v108 static ZIP through a one-use encrypted
Netlify MCP handoff. The proxy credential is never committed or printed."""
import base64, hashlib, json, os, pathlib, sys, time, urllib.parse
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SITE='f0f9cc84-52ab-4bd0-9f39-0c10c8573886'
REPO='airtnqls/Shapez2-Analytics-tools'
RUN=os.environ['GITHUB_RUN_ID']
BRANCH=os.environ['GITHUB_REF_NAME']
assert BRANCH=='deploy/tmam-journal-v108'
zip_path=pathlib.Path(os.environ.get('TMAM_ZIP','tmam-v108-static.zip'))
assert zip_path.is_file()
package=zip_path.read_bytes()
package_sha=hashlib.sha256(package).hexdigest()
API='https://api.github.com/repos/'+REPO
headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'TMAM-v108-deployer'}
session=requests.Session()

def api(method,path,**kwargs):
    r=session.request(method,API+path,headers=headers,timeout=45,**kwargs)
    if r.status_code>=400:
        raise RuntimeError('GitHub API HTTP '+str(r.status_code))
    return r.json()

def put(path,obj):
    content=base64.b64encode(json.dumps(obj,indent=2).encode()).decode()
    api('PUT','/contents/'+path,json={'branch':BRANCH,'message':'deploy(tmam): '+path.rsplit('/',1)[-1],'content':content})

def read(path):
    r=session.get(API+'/contents/'+path,headers=headers,params={'ref':BRANCH},timeout=45)
    if r.status_code==404:return None
    if r.status_code!=200:raise RuntimeError('GitHub read HTTP '+str(r.status_code))
    return json.loads(base64.b64decode(r.json()['content']))

key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
pem=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
challenge=base64.b64encode(os.urandom(24)).decode()
aad=('TMAM-v108:'+RUN+':'+SITE+':'+challenge).encode()
request={'schema':'tmam.deploy.handoff.v1','version':'v108','run_id':RUN,'site_id':SITE,
         'public_key':pem,'challenge':challenge,'created_at':int(time.time()),
         'expires_at':int(time.time())+1200,'release_sha256':package_sha}
put('tmam-story/handshake/request-'+RUN+'.json',request)
print('HANDOFF_REQUEST '+RUN,flush=True)
deadline=time.monotonic()+1200
reply=None
while time.monotonic()<deadline:
    reply=read('tmam-story/handshake/response-'+RUN+'.json')
    if reply is not None:break
    time.sleep(5)
if reply is None:raise RuntimeError('Handoff deadline reached')
assert reply['schema']==request['schema'] and reply['run_id']==RUN and reply['site_id']==SITE
assert reply['challenge']==challenge
secret=key.decrypt(base64.b64decode(reply['wrapped_key'],validate=True),
    padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=b'tmam-netlify'))
plain=AESGCM(secret).decrypt(base64.b64decode(reply['nonce'],validate=True),
    base64.b64decode(reply['ciphertext'],validate=True),aad)
message=json.loads(plain)
proxy=message['proxy_url'].rstrip('/')
parsed=urllib.parse.urlparse(proxy)
assert parsed.scheme=='https' and parsed.hostname=='netlify-mcp.netlify.app' and parsed.path.startswith('/proxy/')
assert message['site_id']==SITE and not parsed.query and not parsed.fragment
print('::add-mask::'+proxy,flush=True)
print('::add-mask::'+parsed.path.removeprefix('/proxy/'),flush=True)
try:
    r=requests.post(proxy+'/api/v1/sites/'+SITE+'/builds',
        files={'zip':('tmam-v108.zip',package,'application/zip')},
        headers={'User-Agent':'netlify-mcp'},timeout=(30,360),allow_redirects=False)
except requests.RequestException:
    raise RuntimeError('Netlify upload network error') from None
if r.status_code not in (200,201,202):raise RuntimeError('Netlify upload HTTP '+str(r.status_code))
data=r.json();data=data[0] if isinstance(data,list) else data
deploy_id=data.get('deploy_id');assert deploy_id
result={'version':'v108','site_id':SITE,'deploy_id':deploy_id,'build_id':data.get('id'),
        'zip_sha256':package_sha,'run_id':RUN,'state':'submitted'}
end=time.monotonic()+900
while time.monotonic()<end:
    try:
        rr=requests.get(proxy+'/api/v1/deploys/'+deploy_id,headers={'User-Agent':'netlify-mcp'},timeout=30)
        if rr.status_code!=200:time.sleep(5);continue
        d=rr.json();state=d.get('state')
    except Exception:
        time.sleep(5);continue
    if state in ('ready','error','rejected'):
        result.update(state=state,url=d.get('ssl_url') or d.get('url'),published_at=d.get('published_at'),context=d.get('context'))
        break
    time.sleep(5)
else:result['state']='verification_timeout'
pathlib.Path('deployment-v108.json').write_text(json.dumps(result,indent=2))
put('tmam-story/deployments/'+RUN+'.json',result)
print(json.dumps(result),flush=True)
if result['state']!='ready':raise RuntimeError('Deployment not ready')
