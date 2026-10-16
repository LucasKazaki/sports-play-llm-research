"""Direct/transitive source corruption fixtures; no corpus/framework assets."""
from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import prepare_v2 as p

def binding(path):return {'path':str(path),'sha256':p.digest(path)}

def setup(tmp_path):
    transitive=tmp_path/'transitive.py';transitive.write_text('authored source')
    parent=tmp_path/'parent.json';parent.write_text(json.dumps({'schema':'chess.conditional-target-export.v1','dependencies':[binding(transitive)]}))
    return {'dependencies':[binding(Path(p.targets.native.__file__))], 'target_export_protocol':binding(parent)},transitive

def test_transitive_source_tamper_is_rejected_before_tokenizer_import(tmp_path):
    plan,source=setup(tmp_path);assert p.verify_tokenizer_sources(plan)
    source.write_text('changed source')
    with pytest.raises(ValueError,match='Frozen bytes'):p.verify_tokenizer_sources(plan)
    assert 'torch'not in sys.modules and 'transformers'not in sys.modules

def test_direct_native_missing_or_wrong_digest_is_rejected(tmp_path):
    plan,source=setup(tmp_path);plan['dependencies']=[]
    with pytest.raises(ValueError,match='Direct actual native'):p.verify_tokenizer_sources(plan)
    plan['dependencies']=[{'path':str(Path(p.targets.native.__file__)),'sha256':'0'*64}]
    with pytest.raises(ValueError,match='Frozen bytes'):p.verify_tokenizer_sources(plan)
