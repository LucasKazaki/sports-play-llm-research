"""Pinned, anonymous Queen acquisition; downloads files, executes no model code."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
REPO_ID = 'princeton-nlp/queen_pawn-8'
REVISION = '5027687fac08b64b2403b13aca5b198e68294fe9'
OUT = ROOT/'data/private/chess-queen-v1/pawn-8'

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024**2),b''):value.update(chunk)
    return value.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base=f'https://huggingface.co/{REPO_ID}/resolve/{REVISION}/'
    release_bytes=urlopen(base+'release.json',timeout=60).read(1_000_000)
    release=json.loads(release_bytes)
    (OUT/'release.json').write_bytes(release_bytes)
    def download(item):
        name,record=item
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe release path')
        path=OUT/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.stat().st_size!=record['bytes'] or digest(path)!=record['sha256']:
                raise ValueError('existing pinned asset differs: '+name)
            return name,record
        part=path.with_name(path.name+'.part')
        # Atomic completion; interrupted bytes never become a loadable asset.
        with urlopen(Request(base+name,headers={'User-Agent':'Archit-local-research/1'}),timeout=120) as response, part.open('wb') as output:
            count=0
            while chunk:=response.read(4*1024**2):
                count+=len(chunk)
                if count>record['bytes']:raise ValueError('asset exceeds pinned byte bound: '+name)
                output.write(chunk)
        if count!=record['bytes'] or digest(part)!=record['sha256']:
            raise ValueError('asset bytes/hash differ: '+name)
        part.replace(path)
        print(json.dumps({'completed':name,'bytes':count}),flush=True)
        return name,record
    with ThreadPoolExecutor(max_workers=2) as pool:
        files=dict(pool.map(download,release['files'].items()))
    receipt={'schema':'chess.queen-acquisition.v1','created_at':datetime.now(timezone.utc).isoformat(),
        'repo_id':REPO_ID,'revision':REVISION,'anonymous_public_download':True,
        'release_sha256':hashlib.sha256(release_bytes).hexdigest(),'files':files,
        'purpose':'Private local research, as explicitly authorized; no weight redistribution.',
        'rights_notes':{'queen_source':'Apache-2.0 at pinned GitHub source c372da22ca75e95c3c79bee8a83c220fc54d0dcb',
            'base_decoder':'SmolLM3-3B, Apache-2.0 declared by upstream model card',
            'encoder':'LC0 BT5; upstream component terms apply. LC0 engine source is GPL-3.0-or-later; this does not establish a separate permissive license for the converted network.',
            'combined_release':'Publisher explicitly asserts no blanket combined license; not represented as Apache/MIT licensed weights. Local research acquisition authorized by task owner after this finding; no accounts, terms acceptance or access gate.'},
        'executed_remote_python':False,'pretrained_forwards':0}
    target=OUT.parent/'acquisition.json'
    target.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'receipt':str(target),'files':len(files),'bytes':sum(r['bytes'] for r in files.values())}),flush=True)

if __name__=='__main__':main()
