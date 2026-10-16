"""Separate optional192 preview; never changes or stops the current tutor."""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
from runner import PreviewRunner,Unavailable,child

_BASE=None


def base_module():
    global _BASE
    if _BASE is None:
        spec=importlib.util.spec_from_file_location('_archit_tutor_preview_frozen_base',ROOT/'prototype/chess_tutor_v1/server.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);_BASE=module
    return _BASE


def verify_sources(path,expected_sha):
    child.require(type(expected_sha) is str and child.safe.HEX.fullmatch(expected_sha)
        and child.digest(path)==expected_sha,'An exact preview source manifest hash is required.')
    manifest=child.read_json(path)
    child.require(manifest.get('schema')=='chess.daytime192-preview-sources.v1'
        and type(manifest.get('files')) is list and manifest['files'],'Missing source closure.')
    for item in manifest['files']:child.inside(ROOT,item)
    return manifest


def preview_packet(payload):
    packet,context,terminal=base_module().coach_packet(payload)
    current={key:value for key,value in packet.items() if key in {'fen','selected_uci'}}
    child.packet(current) # Validate the actual reduced input, before allocation.
    return current,context,terminal


def page_asset(path):
    # Deliberately not a general-purpose filesystem route.
    names={'/':('index.html','text/html'),'/preview.css':('preview.css','text/css')}
    if path not in names:return None
    name,mime=names[path]
    return (HERE/'static'/name).read_bytes(),mime+'; charset=utf-8'


def preview_handler(tutor,coaching):
    parent=base_module().handler_for(tutor,coaching)
    class Handler(parent):
        def do_GET(self):
            asset=page_asset(self.path.split('?',1)[0])
            if asset is None:return super().do_GET()
            if self._local():self._send(200,*asset)
    return Handler


def components(qualification=None,qualification_sha256=None):
    base=base_module();runner=None;reason=None
    try:runner=PreviewRunner(ROOT,qualification,qualification_sha256)
    except Unavailable as error:reason=str(error)
    jobs=base.CoachingJobs(ROOT/'data/private/chess-tutor-daytime192-v1/coaching',preview_packet,runner)
    if reason:jobs.blocked=reason
    # Constructors are lazy. Only future explicit board analysis starts an engine;
    # this process never allocates a CPU classifier or an automatic Queen request.
    tutor=base.Tutor(base.Engine(),base.Classifier(None))
    return tutor,jobs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-manifest',type=Path,default=ROOT/'experiments/chess-tutor-daytime192-v1/source-manifest.json')
    parser.add_argument('--source-manifest-sha256',required=True)
    parser.add_argument('--qualification',type=Path);parser.add_argument('--qualification-sha256')
    args=parser.parse_args()
    verify_sources(args.source_manifest,args.source_manifest_sha256)
    tutor,jobs=components(args.qualification,args.qualification_sha256)
    base=base_module();server=base.ThreadingHTTPServer(('127.0.0.1',8795),preview_handler(tutor,jobs))
    try:server.serve_forever()
    finally:jobs.close();server.server_close()


if __name__=='__main__':main()
