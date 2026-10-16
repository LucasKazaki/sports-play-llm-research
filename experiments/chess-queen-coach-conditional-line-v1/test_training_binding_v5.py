"""Real bound relative/absolute parent metadata; no actual corpus/backend."""
from pathlib import Path
import sys,json,copy
import pytest
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import prepare_training_v5 as b
import training_contract_v2 as c

def test_relative_parent_and_absolute_target_manifest_resolve_to_same_bound_identity(tmp_path,monkeypatch):
    def file(name,value):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return path
    source=file('data/private/authored-parent.json',{'status':'authored'})
    relative={'path':'data/private/authored-parent.json','sha256':b.binding(source)['sha256']}
    parent={key:{'authored':key}for key in c.SAME};parent.update(corpus_manifest=relative,daytime_authority={},dependencies=[])
    parent_path=file('parent.json',parent);audit=file('audit.json',{})
    selection=file('selection.json',{'status':'selected','selected':{'step':192,'candidate_id':'queen-pawn-8/nf4-coach-counterfactual-v1'}})
    data=tmp_path/'new';data.mkdir();child={'parent_manifest':b.binding(source),'files':{name:{'sha256':'authored'}for name in ['train.jsonl','development.jsonl','development-references.jsonl']}}
    (data/'manifest.json').write_text(json.dumps(child))
    metadata=[file(name,{})for name in ['export.json','closed.json','token-plan.json','token-result.json','data-audit.json']]
    monkeypatch.setattr(c,'ROOT',tmp_path)
    plan=b.common(parent_path,audit,selection,data,*metadata)
    assert plan['parent_corpus_manifest']==child['parent_manifest']
    assert Path(plan['parent_corpus_manifest']['path']).is_absolute()
    assert c.bound(plan['parent_corpus_manifest'])==source
    # Canonicalization cannot bless a same-path wrong digest.
    parent['corpus_manifest']['sha256']='0'*64;parent_path.write_text(json.dumps(parent))
    with pytest.raises(ValueError,match='Frozen bytes'):b.common(parent_path,audit,selection,data,*metadata)


def test_all_other_future_builder_function_bodies_are_preserved_except_source_metadata():
    import ast
    def functions(name):return {n.name:ast.dump(n)for n in ast.parse((HERE/name).read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef)}
    old=functions('prepare_training_v4.py');new=functions('prepare_training_v5.py')
    assert {name for name in old if old[name]!=new[name]}=={'common'}
    for name in ['prepare_qualification','prepare_training']:assert old[name]==new[name]
