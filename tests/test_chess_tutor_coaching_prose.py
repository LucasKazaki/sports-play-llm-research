"""Exercise actual presentation code while retaining the exact raw response."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_explanation_presentation_preserves_unverified_prose_and_raw_record():
    node=shutil.which('node')
    if not node:pytest.skip('Node is not installed')
    source=Path(__file__).resolve().parents[1]/'prototype/chess_tutor_v1/static/coaching.js'
    program=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const prefix=fs.readFileSync(process.argv[1],'utf8').split('(() => {')[0];
const context={};vm.runInNewContext(prefix+';globalThis.draft=coachingDraftText;',context);
const raw=Object.freeze({decoded_text:'ANALYSIS:\nA disputed claim.\n\nAn illegal side variation stays visible.\nBEST_MOVE: move\nCRITICAL_LINE: line\nEVALUATION: +99<|im_end|>',raw_text:'EXACT ORIGINAL'});
const before=JSON.stringify(raw),display=context.draft(raw);
assert.equal(display,'A disputed claim.\n\nAn illegal side variation stays visible.');
assert.equal(JSON.stringify(raw),before);
assert.equal(context.draft({raw_text:'Partial <script>alert(1)</script>'}),'Partial <script>alert(1)</script>');
assert.equal(context.draft({decoded_text:'ANALYSIS:\nA short draft.<|im_end|>'}),'A short draft.');
assert.equal(context.draft({error:'Backend error retained'}),'Backend error retained');
'''
    subprocess.run([node,'-e',program,str(source)],check=True,capture_output=True,text=True)
