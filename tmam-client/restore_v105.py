#!/usr/bin/env python3
"""Reassemble the audited English release; no credentials or user data."""
import base64, hashlib, json, lzma, pathlib
root=pathlib.Path(__file__).resolve().parent
packed=bytearray(base64.b64decode(''.join((root/'v105-exact'/f'part-{i:02}.b64').read_text().strip() for i in range(14)),validate=True))
# Correct the LZMA2 chunk length after completing the interrupted stream.
assert packed[61470:61474] in (bytes.fromhex('3e40da4a'),bytes.fromhex('4a52de3e'))
packed[61470:61474]=bytes.fromhex('4a52de3e')
assert hashlib.sha256(packed).hexdigest()=='ea3dcd55b120691086621560c880657a559a8f63edef74bd515fc3472ff6e3d6','compressed source SHA mismatch'
raw=lzma.decompress(packed,memlimit=256*1024*1024)
assert hashlib.sha256(raw).hexdigest()=='5f64a06f3295275e5a911c73b933c34b6373c1540346610e75fb4cbcd5906c48','source SHA mismatch'
files=json.loads(raw);assert len(files)==42
out=root/'release';out.mkdir(exist_ok=True)
for name,entry in files.items():
    path=pathlib.PurePosixPath(name)
    assert not path.is_absolute() and '..' not in path.parts
    assert path.parts[0] in ('site','generator','reconstruct.py','smoke.cjs')
    data=entry['text'].encode() if 'text' in entry else base64.b64decode(entry['b64'],validate=True)
    dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
print(json.dumps({'status':'VERIFIED_SOURCE_RESTORED','files':len(files),'source_sha256':hashlib.sha256(raw).hexdigest()}))
