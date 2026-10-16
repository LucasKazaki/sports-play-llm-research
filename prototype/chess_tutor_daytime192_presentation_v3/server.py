"""Default-off asset overlay; unchanged192 admission/runtime on separate8796."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'prototype/chess_tutor_daytime192_v1'
FILES=tuple('prototype/chess_tutor_daytime192_presentation_v3/'+name for name in
    ('server.py','prepare_manifest.py','static/app.js','static/coaching.js','test_presentation_v3.py','test_rendering_v3.js'))
_PREVIOUS=None


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def previous():
    global _PREVIOUS
    if _PREVIOUS is None:
        sys.path.insert(0,str(OLD))
        spec=importlib.util.spec_from_file_location('_archit_daytime192_presentation_parent',OLD/'server.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);_PREVIOUS=module
    return _PREVIOUS


def verify_overlay(path,expected_sha,original_manifest,original_sha):
    if digest(path)!=expected_sha:raise ValueError('Exact extra presentation manifest required')
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    rows=value.get('files',[])
    if(value.get('schema')!='chess.daytime192-presentation-sources.v3'
        or len(rows)!=len(FILES)or {row['path']for row in rows}!=set(FILES)):
        raise ValueError('Exact presentation-only source closure required')
    parent=value.get('original_192_source_manifest',{})
    if(Path(parent.get('path','')).resolve()!=Path(original_manifest).resolve()
        or parent.get('sha256')!=original_sha):raise ValueError('Original192 source manifest binding differs')
    for row in rows:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Presentation source changed: '+row['path'])
    return value


def page_asset(path):
    names={'/app.js':'app.js','/coaching.js':'coaching.js'}
    if path not in names:return None
    return (HERE/'static'/names[path]).read_bytes(),'text/javascript; charset=utf-8'


def handler(tutor,jobs):
    parent=previous().preview_handler(tutor,jobs)
    class Handler(parent):
        def do_GET(self):
            asset=page_asset(self.path.split('?',1)[0])
            if asset is None:return super().do_GET()
            if self._local():self._send(200,*asset)
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve',action='store_true',help='Explicitly start the separate presentation server; no model admission follows.')
    parser.add_argument('--source-manifest',type=Path,required=True)
    parser.add_argument('--source-manifest-sha256',required=True)
    parser.add_argument('--presentation-manifest',type=Path,required=True)
    parser.add_argument('--presentation-manifest-sha256',required=True)
    parser.add_argument('--qualification',type=Path);parser.add_argument('--qualification-sha256')
    args=parser.parse_args()
    if not args.serve:raise SystemExit('Presentation server remains off; explicit --serve is required.')
    verify_overlay(args.presentation_manifest,args.presentation_manifest_sha256,args.source_manifest,args.source_manifest_sha256)
    parent=previous();parent.child.before_cutoff()
    parent.verify_sources(args.source_manifest,args.source_manifest_sha256)
    tutor,jobs=parent.components(args.qualification,args.qualification_sha256)
    server=parent.base_module().ThreadingHTTPServer(('127.0.0.1',8796),handler(tutor,jobs))
    try:server.serve_forever()
    finally:jobs.close();server.server_close()


if __name__=='__main__':main()
