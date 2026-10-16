"""Authored source/asset/renderer checks; never start a server or model."""
import importlib.util,json,shutil,subprocess
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('presentation_overlay_authored',HERE/'server.py')
subject=importlib.util.module_from_spec(spec);spec.loader.exec_module(subject)


def test_only_exact_readonly_overlay_routes():
    for route,name in [('/app.js','app.js'),('/coaching.js','coaching.js')]:
        data,mime=subject.page_asset(route)
        assert data==(HERE/'static'/name).read_bytes()and mime=='text/javascript; charset=utf-8'
    for route in ['/','/api/coach','/../server.py','/app.js/../server.py','/coaching.js?x=1']:
        assert subject.page_asset(route)is None
    assert subject._PREVIOUS is None  # Import and asset reads cannot allocate old components.


def test_extra_manifest_requires_exact_sources_and_original_manifest(tmp_path,monkeypatch):
    repo=tmp_path/'repo';repo.mkdir();monkeypatch.setattr(subject,'ROOT',repo)
    original=tmp_path/'original.json';original.write_text('{}');source_sha=subject.digest(original)
    files=[]
    for name in subject.FILES:
        path=repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('authored')
        files.append({'path':name,'sha256':subject.digest(path)})
    value={'schema':'chess.daytime192-presentation-sources.v3','files':files,
        'original_192_source_manifest':{'path':str(original),'sha256':source_sha}}
    manifest=tmp_path/'extra.json';manifest.write_text(json.dumps(value))
    assert subject.verify_overlay(manifest,subject.digest(manifest),original,source_sha)==value
    files[0]['sha256']='tampered';manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='source changed'):subject.verify_overlay(manifest,subject.digest(manifest),original,source_sha)
    with pytest.raises(ValueError,match='Original192'):subject.verify_overlay(manifest,subject.digest(manifest),original,'other')


def test_no_new_runtime_or_admission_route_in_overlay_source():
    text=(HERE/'server.py').read_text(encoding='utf-8-sig')
    assert "('127.0.0.1',8796)"in text and "if not args.serve:raise SystemExit"in text
    assert 'parent.verify_sources(args.source_manifest,args.source_manifest_sha256)'in text
    assert 'parent.components(args.qualification,args.qualification_sha256)'in text
    assert 'parent.child.before_cutoff()'in text
    assert all(value not in text for value in ['import torch','import transformers','8793','8795'])


def test_authored_control_and_renderer_behaviors():
    node=shutil.which('node')
    if node is None:pytest.skip('Node runtime unavailable; renderer qualification remains unrun')
    result=subprocess.run([node,str(HERE/'test_rendering_v3.js')],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
