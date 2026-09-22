#!/usr/bin/env python3
"""Reconstruct the audited v105 source payload; no credentials are involved."""
import base64,hashlib,json,lzma,pathlib,re,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
META={'sources':[{'path':'assets/app-v100.css','sha256':'93bfefb95dda4b356eae8677037e8276b8245c670340e0779089ca3c38fb37fa'},{'path':'assets/app-v100.js','sha256':'78c6da291596855eda721aa6f234afd8dfdc70122d2a8665822b908328fc957c'},{'path':'assets/catalog-v99.js','sha256':'ffcd228b52303ca5f60321b3279aa9d03e0989ae448c0293323ef83f82341d42'},{'path':'assets/count-v100.wasm','sha256':'83f4406aab72c61e9e70cfab2587ee64c9d2e785eee3f960690df607ff4976b0'},{'path':'assets/icon.svg','sha256':'36c74de021024bfcf1fe2563ba3496a0ef065f6564d00f3295e0a2a328751cab'},{'path':'assets/runtime-v100.js','sha256':'1b10724ad556489eeaa162ab98005ccaae6ef6c7223f452a4d6112ad1fe4654b'},{'path':'assets/search-worker-v100.js','sha256':'b063653cef693fe476e3a2ee2f9af500591cafe978a965bd1fead166018de2d8'},{'path':'assets/transport-v100.js','sha256':'7202d5d36cc9cb3c33d0c0d957cb91eb317a7b87b8d44b25dbbb8c21e2b11f6f'},{'path':'index.html','sha256':'6969acde8cd0c3886584a5a75013e2c2f94938e542d7cf09e11313d704b1c194'},{'path':'studio/index.html','sha256':'50451b9007960a19d9b015f7aa8deea06c665372a33c8b1b8dde926c2ba69720'}],'base_sha256':'82f358cbc0eec6f89be5c553d7d0840f5e99a36830c4c03a50297f0418f32678','payload_sha256':'701ac22158a6f2a1f1eb3553fbf00a8e82fb65e9ca99dc3f3add07e68bfb6525','files':42}
def sha(b):return hashlib.sha256(b).hexdigest()
parts=[]
for entry in META['sources']:
 req=urllib.request.Request('https://tmam-web.netlify.app/'+entry['path'],headers={'User-Agent':'TMAM-v105-source-restore','Accept-Encoding':'identity'})
 with urllib.request.urlopen(req,timeout=90) as r:b=r.read(20000000)
 assert sha(b)==entry['sha256'],entry['path']
 if entry['path']=='studio/index.html':b=re.sub(rb'(<script[^>]*type="application/json"[^>]*>).*?(</script>)',rb'\1\2',b,flags=re.S)
 parts.append(b)
base=b'\n'.join(parts);assert sha(base)==META['base_sha256']
encoded=''.join((ROOT/'payload'/f'{n:03}.b64').read_text().strip() for n in range(18))
packed=base64.b64decode(encoded,validate=True);assert sha(packed)==META['payload_sha256'],'payload SHA mismatch'
data=lzma.decompress(packed,memlimit=256*1024*1024);assert data[:8]==b'TMAMPCH1'
pos=8

def integer():
 global pos
 n=0;s=0
 while True:
  b=data[pos];pos+=1;n|=(b&127)<<s
  if b<128:return n
  s+=7
  assert s<64

def take(n):
 global pos
 assert 0<=n<=len(data)-pos
 b=data[pos:pos+n];pos+=n;return b

count=integer();assert count==META['files']
out=ROOT/'restored';out.mkdir(exist_ok=True)
for _ in range(count):
 path=take(integer()).decode();p=pathlib.PurePosixPath(path)
 assert not p.is_absolute() and '..' not in p.parts and p.parts[0] in ['site','generator','reconstruct.py','smoke.cjs']
 size=integer();expected=take(32).hex();length=integer();end=pos+length;result=bytearray()
 while pos<end:
  op=take(1)[0]
  if op==0:result.extend(take(integer()))
  elif op==1:
   start=integer();amount=integer();assert start+amount<=len(base);result.extend(base[start:start+amount])
  else:raise ValueError('invalid delta operation')
 assert pos==end and len(result)==size and sha(result)==expected,path
 dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(result)
assert pos==len(data)
print(json.dumps({'status':'SOURCE_RESTORED','files':count,'payload_sha256':sha(packed)}),flush=True)
