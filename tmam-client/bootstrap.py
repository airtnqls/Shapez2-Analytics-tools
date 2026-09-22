"""Preserve the existing public TMAM catalog, validating its canonical bytes."""
import concurrent.futures
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import urllib.request
import zipfile

BASE = 'https://tmam-web.netlify.app/'
MANIFEST_SHA = '94e9562fa2a01d3ad48f848c067fc081e0d0c7b73b9441c3ed2529d6232207ff'
OUT = Path('baseline')


def get(path):
    if path.startswith('/') or '..' in path.split('/') or ':' in path:
        raise ValueError('Unsafe asset path')
    request = urllib.request.Request(BASE + path, headers={'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def canonical(encoded, meta):
    if meta.get('encoding') != 'node-delta':
        assert len(encoded) == meta['bytes']
        return encoded
    assert len(encoded) == meta['encoded_bytes'] and meta['bytes'] % 12 == 0
    out = bytearray(meta['bytes'])
    pos = 0
    def varint():
        nonlocal pos
        value = 0
        for shift in range(0, 35, 7):
            if pos >= len(encoded):
                raise ValueError('Truncated relative node index')
            b = encoded[pos]; pos += 1
            if shift == 28 and b & 240:
                raise ValueError('Relative node index overflow')
            value |= (b & 127) << shift
            if not b & 128:
                return value
        raise ValueError('Invalid relative node index')
    for k in range(meta['bytes'] // 12):
        v = encoded[pos]; pos += 1
        i = meta['first_node'] + k
        lo, hi = varint(), varint()
        assert 0 <= v < 64 and 1 <= lo <= i and 1 <= hi <= i
        struct.pack_into('<III', out, 12*k, v, i-lo, i-hi)
    assert pos == len(encoded)
    return out


def main():
    OUT.mkdir(exist_ok=True)
    manifest_bytes = get('data/manifest-v100.json')
    assert hashlib.sha256(manifest_bytes).hexdigest() == MANIFEST_SHA
    manifest = json.loads(manifest_bytes)
    (OUT/'data').mkdir(exist_ok=True)
    (OUT/'data/manifest-v100.json').write_bytes(manifest_bytes)
    chunks = {}
    for cap in manifest['caps'].values():
        for source in cap['sources'].values():
            for part in source['chunks']:
                chunks[part['url']] = part
    def copy_part(item):
        path, meta = item
        packed = get(path)
        raw = canonical(gzip.decompress(packed), meta)
        assert len(packed) == meta['download_bytes'], path
        assert len(raw) == meta['bytes'], path
        assert hashlib.sha256(raw).hexdigest() == meta['sha256'], path
        target = OUT/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(packed)
        return len(packed)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        sizes = list(pool.map(copy_part, chunks.items()))
    for path in ['studio/index.html', 'assets/catalog-v99.js']:
        data = get(path)
        target = OUT/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        print(json.dumps({'source': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}))
    summary = {'manifest_sha256': MANIFEST_SHA, 'verified_chunks': len(chunks), 'download_bytes': sum(sizes), 'files': {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file()}}
    Path('baseline-audit.json').write_text(json.dumps(summary, indent=2))
    with zipfile.ZipFile('tmam-v100-verified-baseline.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():
                info = zipfile.ZipInfo(str(p.relative_to(OUT)), (1980,1,1,0,0,0)); info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
    archive = Path('tmam-v100-verified-baseline.zip')
    print(json.dumps({'verified_chunks': len(chunks), 'archive_bytes': archive.stat().st_size, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
