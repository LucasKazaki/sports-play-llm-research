"""Small sealed-vector and metadata fixtures, never real-data selection."""
import copy
import json
from pathlib import Path
import shutil
import sys

import chess
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import chess_matched_check_intake as intake


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding="utf-8")


@pytest.fixture
def bound_metadata(tmp_path):
    repo,workspace=tmp_path/"repo",tmp_path/"workspace"
    repo.mkdir();workspace.mkdir()
    files={}
    for module in (intake.core,intake.prior,intake.prior.historical):
        src=Path(module.__file__);target=repo/"scripts"/src.name;target.parent.mkdir(exist_ok=True)
        shutil.copyfile(src,target)
        files["scripts/"+src.name]={"bytes":target.stat().st_size,"sha256":intake.sha(target)}
    (repo/"only-fixture.txt").write_text("fixed",encoding="utf-8")
    files["only-fixture.txt"]={"bytes":5,"sha256":intake.sha(repo/"only-fixture.txt")}
    (workspace/"review.json").write_text("{}",encoding="utf-8")
    archived="experiments/chess-matched-check-v1/archive/v1/source-and-exclusion-metadata.json"
    path=repo/archived;path.parent.mkdir(parents=True)
    shutil.copyfile(intake.ROOT/archived,path)
    protocol={"evidence_before_new_work":{"all_frozen_existing_inputs_sha256":files,
        "additional_workspace_bindings":{"review.json":{"bytes":2,"sha256":intake.sha(workspace/"review.json")}}}}
    return repo,workspace,protocol


def test_bound_files_and_actual_rule_runtime_are_verified(bound_metadata):
    repo,workspace,protocol=bound_metadata
    result=intake.verify_bindings(repo,workspace,protocol)
    assert len(result)==5


@pytest.mark.parametrize("root_name,name",[("repo","only-fixture.txt"),("workspace","review.json")])
def test_byte_or_size_tamper_is_rejected(bound_metadata,root_name,name):
    repo,workspace,protocol=bound_metadata
    path=(repo if root_name=="repo" else workspace)/name
    path.write_text("changed",encoding="utf-8")
    with pytest.raises(ValueError,match="bound input changed"):
        intake.verify_bindings(repo,workspace,protocol)


def test_actual_import_hash_is_not_substituted_by_a_different_repo_copy(bound_metadata):
    repo,workspace,protocol=bound_metadata
    modified=repo/"scripts/chess_board_fact_core.py"
    modified.write_text("# changed copy\n",encoding="utf-8")
    protocol["evidence_before_new_work"]["all_frozen_existing_inputs_sha256"]["scripts/chess_board_fact_core.py"]={
        "bytes":modified.stat().st_size,"sha256":intake.sha(modified)}
    with pytest.raises(ValueError,match="actually imported source changed"):
        intake.verify_bindings(repo,workspace,protocol)


@pytest.fixture
def synthetic_seal(tmp_path):
    repo=tmp_path/"repo";directory=repo/intake.PRIVATE;directory.mkdir(parents=True)
    board=chess.Board("6k1/8/8/8/8/8/8/K1R5 w - - 1 2")
    legal={m.uci() for m in board.legal_moves}
    all_uci=sorted(chess.Move(a,b).uci() for a in chess.SQUARES for b in chess.SQUARES if a!=b)
    labels=sorted(legal)+[uci for uci in all_uci if uci not in legal]
    labels=labels[:1968]
    top=["c1c8","c1g1","c1d1","c1e1","c1f1"]
    rows=[]
    for condition in ("base_classifier_9m","selected_classifier_9m_step512"):
        vector=np.zeros(1968,dtype=np.float32)
        for n,uci in enumerate(top):vector[labels.index(uci)]=10-n
        path=directory/"raw"/(condition+".npy");path.parent.mkdir(exist_ok=True)
        np.save(path,vector,allow_pickle=False)
        items=[{"class_id":labels.index(uci),"move_uci":uci,"logit":float(vector[labels.index(uci)]),"legal":True} for uci in top]
        rows.append({"condition":condition,"status":"completed","id2label":labels,
            "logit_artifact":{"path":"raw/"+path.name,"sha256":intake.sha(path)},
            "raw":{"raw_choice_uci":top[0],"legal_choice_uci":top[0],"raw_choice_is_legal":True,
                   "legal_move_count":len(legal),"raw_topk":items,"legal_topk":copy.deepcopy(items)}})
    rows += [{"condition":name,"status":"completed","parsed":True,"raw_legal":True,"raw_uci":"c1g1"}
             for name in ("base_language_policy_124m","selected_language_policy_124m_v4_step2048")]
    inputs={"positions":[{"case_id":"synthetic","fen":board.fen()}]}
    def reseal():
        write(directory/"move-input.json",inputs)
        write(directory/"raw-results.json",{"rows":rows+[{},{}]})
        write(directory/"move-raw-closed.json",{"rows":rows,"forbid_further_move_calls":True})
        files={p.relative_to(directory).as_posix():intake.sha(p) for p in directory.rglob("*") if p.is_file() and p.name!="raw-seal.json"}
        write(directory/"raw-seal.json",{"planned":6,"conditions":[r["condition"] for r in rows]+["fact0","fact1"],
            "evaluator_opened":False,"files_sha256":files})
    reseal()
    return repo,directory,rows,reseal,board,top


def test_full_synthetic_vectors_and_top_five_reconstruct_successors(synthetic_seal):
    repo,_,_,_,board,top=synthetic_seal
    expected=set()
    for uci in top:
        after=board.copy();after.push_uci(uci);expected.add(intake.prior.board_key(after.fen()))
    assert intake.spent_move_successors(repo)==expected
    assert len(expected)==5


def test_vector_bit_tamper_cannot_pass_existing_raw_seal(synthetic_seal):
    repo,directory,_,_,_,_=synthetic_seal
    path=directory/"raw/base_classifier_9m.npy"
    vector=np.load(path,allow_pickle=False);vector[0]=99
    np.save(path,vector,allow_pickle=False)
    with pytest.raises(ValueError,match="seal mismatch"):intake.spent_move_successors(repo)


@pytest.mark.parametrize("change",["ranking","legal_flag","duplicate_mapping","first_choice","accounting"])
def test_selfsealed_inconsistent_metadata_is_still_rejected(synthetic_seal,change):
    repo,_,rows,reseal,_,_=synthetic_seal
    row=rows[0]
    if change=="ranking":row["raw"]["raw_topk"]=list(reversed(row["raw"]["raw_topk"]))
    elif change=="legal_flag":row["raw"]["raw_topk"][0]["legal"]=False
    elif change=="duplicate_mapping":row["id2label"][1]=row["id2label"][0]
    elif change=="first_choice":row["raw"]["raw_choice_uci"]="c1h1"
    else:row["raw"]["legal_move_count"]+=1
    reseal()
    with pytest.raises(ValueError):intake.spent_move_successors(repo)


def test_partial_retained_closure_is_not_accepted(synthetic_seal):
    repo,_,rows,reseal,_,_=synthetic_seal
    rows[2]["status"]="not_run";reseal()
    with pytest.raises(ValueError,match="incomplete"):intake.spent_move_successors(repo)
