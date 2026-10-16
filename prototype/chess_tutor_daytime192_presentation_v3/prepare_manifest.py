"""Prepare only the additive source manifest; no service or model admission."""
from pathlib import Path
import importlib.util,json
spec=importlib.util.spec_from_file_location('_archit_presentation_manifest_local_server',Path(__file__).with_name('server.py'))
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)


def prepare(repo,original_manifest,original_sha,out):
    repo=Path(repo).resolve();original_manifest=Path(original_manifest).resolve();out=Path(out)
    if out.exists():raise ValueError('Presentation source manifest is create-only')
    if server.digest(original_manifest)!=original_sha:raise ValueError('Original source manifest differs')
    files=[{'path':name,'sha256':server.digest(repo/name)}for name in server.FILES]
    value={'schema':'chess.daytime192-presentation-sources.v3','files':files,
        'original_192_source_manifest':{'path':str(original_manifest),'sha256':original_sha},
        'service_started':False,'model_admission_changed':False,'old_runtime_and_qualification_unchanged':True,
        'port':8796,'cutoff_utc':'2026-10-16T22:00:00+00:00'}
    with out.open('x',encoding='utf-8')as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return {'path':str(out),'sha256':server.digest(out)}
