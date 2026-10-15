"""File-only preselection amendment from a completed sealed illustration."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time

import chess
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT / "work/repos/sports-play-llm-research"
PRIOR = ROOT / "work/chess-matched-check-diagnostic-protocol-v1"
PRIVATE_NAME = "data/private/gothamchess/constructed-middlegame-eval-v1"
PRIVATE = REPO / PRIVATE_NAME


def bind(path):
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return {"bytes":path.stat().st_size,"sha256":digest.hexdigest()}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_new(path, value):
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        stream.write(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n")


def key(board):
    assert not board.chess960 and board.is_valid()
    return " ".join(board.fen().split()[:4])


def main():
    started = time.monotonic()
    assert bind(PRIOR / "FINAL-protocol-PROPOSAL-v1.json")["sha256"] == "3c0afc7f4409fd241cbc705df4f571d435de445e8281079b0691a49d3fe084fa"
    assert bind(PRIOR / "known-history-exclusions.json")["sha256"] == "418e9eb789c6b220dbe6ea915ddc24521d2bd9abdc6c6050fe1230002afb7d7d"
    prior_protocol = read(PRIOR / "FINAL-protocol-PROPOSAL-v1.json")
    prior_registry = read(PRIOR / "known-history-exclusions.json")
    audit_path = ROOT / "outputs/gotham-constructed-middlegame-independent-review.json"
    audit_source = ROOT / "work/audit_gotham_constructed_retained.py"
    assert bind(audit_path)["sha256"] == "4bd2abd5ee1dea8e7a3c204ee7e6bc5512f193c24794bbf94578f4264fcd893d"
    assert bind(audit_source)["sha256"] == "62809b27a8c7d64b9934bf4bea0f8c968e5045dccb0fba9fe0c85673a6394bff"
    assert bind(PRIVATE / "raw-seal.json")["sha256"] == "25af8a8a8a0578935f1585b8040c3b27a75a2a03b9bf01c40bded3a0359f5cb9"
    seal = read(PRIVATE / "raw-seal.json")
    assert seal["planned"] == 6 and seal["evaluator_opened"] is False
    sealed_before = {name:bind(PRIVATE / name) for name in seal["files_sha256"]}
    for name,expected in seal["files_sha256"].items():
        assert sealed_before[name]["sha256"] == expected, name
    audit = read(audit_path)
    assert audit["verdict"] == "SEALED_SIX_OUTCOMES_NATIVE_TOKENS_LOGITS_RULE_FACTS_AND_RECOUNT_MATCH"
    assert audit["raw_seal_sha256"] == bind(PRIVATE / "raw-seal.json")["sha256"]
    assert audit["planned"] == audit["completed_raw"] == 6
    assert audit["new_model_engine_calls"] == 0
    closed = read(PRIVATE / "move-raw-closed.json")
    assert len(closed["rows"]) == 4
    assert closed["forbid_further_move_calls"] is True
    raw = read(PRIVATE / "raw-results.json")
    move_rows = raw["rows"][:4]
    assert move_rows == closed["rows"]
    assert [r["condition"] for r in move_rows] == seal["conditions"][:4]
    inputs = read(PRIVATE / "move-input.json")["positions"]
    assert len(inputs) == 1
    board = chess.Board(inputs[0]["fen"])
    assert key(board) in prior_registry["board_keys"]
    legal_moves = {move.uci() for move in board.legal_moves}
    occurrences, verified_classifiers = [], []

    def record(condition, kind, uci, class_id=None):
        assert type(uci) is str
        move = chess.Move.from_uci(uci)
        legal = move in board.legal_moves
        row = {"condition":condition,"role":kind,"move_uci":uci,"legal":legal}
        if class_id is not None:
            row["class_id"] = class_id
        if legal:
            after = board.copy(stack=False)
            after.push(move)
            row.update(successor_fen=after.fen(),successor_key=key(after))
        occurrences.append(row)

    for row in move_rows:
        assert row["status"] == "completed"
        condition = row["condition"]
        if "classifier" in condition:
            artifact = row["logit_artifact"]
            vector_path = (PRIVATE / artifact["path"]).resolve()
            assert vector_path.is_relative_to(PRIVATE.resolve())
            assert bind(vector_path)["sha256"] == artifact["sha256"]
            vector = np.load(vector_path,allow_pickle=False)
            labels = row["id2label"]
            assert vector.shape == (1968,) and vector.dtype == np.float32 and np.isfinite(vector).all()
            assert type(labels) is list and len(labels) == len(set(labels)) == len(vector)
            ranked = sorted(range(len(vector)),key=lambda i:(-float(vector[i]),i))
            legal_ranked = [i for i in ranked if labels[i] in legal_moves]
            result = row["raw"]
            assert result["raw_choice_uci"] == labels[ranked[0]]
            assert result["legal_choice_uci"] == labels[legal_ranked[0]]
            assert result["raw_choice_is_legal"] == (labels[ranked[0]] in legal_moves)
            assert result["legal_move_count"] == len(legal_moves)
            record(condition,"first_raw_choice",result["raw_choice_uci"])
            record(condition,"first_legal_masked_choice",result["legal_choice_uci"])
            for name,expected_ids in (("raw_topk",ranked[:5]),("legal_topk",legal_ranked[:5])):
                top = result[name]
                assert [item["class_id"] for item in top] == expected_ids
                for item,index in zip(top,expected_ids,strict=True):
                    assert item["move_uci"] == labels[index]
                    assert item["logit"] == float(vector[index])
                    assert item["legal"] == (labels[index] in legal_moves)
                    record(condition,name,item["move_uci"],index)
            verified_classifiers.append({"condition":condition,"vector":artifact,"mapping_count":len(labels),
                                         "raw_top5": [labels[i] for i in ranked[:5]],
                                         "legal_masked_top5":[labels[i] for i in legal_ranked[:5]]})
        else:
            assert row["parsed"] is True and row["raw_legal"] is True
            record(condition,"first_raw_choice",row["raw_uci"])
    assert len(verified_classifiers) == 2
    all_moves = sorted({item["move_uci"] for item in occurrences if item["legal"]})
    successor_keys = {item["successor_key"] for item in occurrences if item["legal"]}
    old_boards = set(prior_registry["board_keys"])
    added_boards = sorted(successor_keys-old_boards)
    boards = old_boards | successor_keys
    assert all_moves == ["c3d3","c3g3","c3h3","c4d3","d1c1","d1d8","h2h3"]
    assert len(successor_keys) == 7 and len(added_boards) == 6
    assert len(boards) == 71463 and len(prior_registry["games"]) == 30280
    new_files = ["raw-seal.json","raw-results.json","move-raw-closed.json","move-raw-seal.json",
                 "outcome-ledger.json","move-input.json","fact-input.json",
                 "raw/base_classifier_9m.npy","raw/selected_classifier_9m_step512.npy",
                 "sources/local_backends.py","sources/owned_native.py","sources/illustration_core.py",
                 "sources/reviewed-source-bindings.json","sources/reviewed/chess_fact_sft_common.py",
                 "sources/reviewed/chess_native_resources.py"]
    new_repo_bindings = {PRIVATE_NAME+"/"+name:bind(PRIVATE/name) for name in new_files}
    workspace_bindings = {"outputs/gotham-constructed-middlegame-independent-review.json":bind(audit_path),
                          "work/audit_gotham_constructed_retained.py":bind(audit_source)}
    prior_bindings = {"protocol":bind(PRIOR / "FINAL-protocol-PROPOSAL-v1.json"),
                      "known_registry":bind(PRIOR / "known-history-exclusions.json"),
                      "metadata_report":bind(PRIOR / "source-and-exclusion-metadata.json")}
    amendment_stage = {"games":30280,"board_keys":71463,"completed_move_conditions":4,
                       "classifier_vectors_replayed":2,"move_choice_top5_occurrences":len(occurrences),
                       "distinct_legal_move_choices":len(all_moves),"new_successor_board_keys":len(added_boards),
                       "new_game_ids":0}
    registry = deepcopy(prior_registry)
    registry.update(schema="chess.matched-check.known-history-registry.metadata.v2",
                    status="Additive known-spent-state amendment only; no new cohort selected",board_keys=sorted(boards),
                    prior_v1_bindings=prior_bindings,additional_repo_source_bindings=new_repo_bindings,
                    additional_workspace_source_bindings=workspace_bindings)
    registry["stages"]["completed_gotham_first_choices_and_raw_masked_top5_successors"] = amendment_stage
    registry["limitations"][1] = "Only completed sealed illustration move outputs/top5 were inspected for additional spent board exclusions; no active outputs or new candidate positions were inspected."
    save_new(HERE / "known-history-exclusions-v2.json",registry)
    report = {
        "schema":"chess.matched-check.spent-state-amendment-audit.v2",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "status":"PASS: completed sealed moves/top5 and additive successor union match",
        "prior_v1_bindings":prior_bindings,"additional_repo_source_bindings":new_repo_bindings,
        "additional_workspace_source_bindings":workspace_bindings,
        "raw_sealed_files_verified_before":sealed_before,"raw_sealed_files_verified_after":{name:bind(PRIVATE/name) for name in seal["files_sha256"]},
        "classifiers":verified_classifiers,"move_occurrences":occurrences,
        "distinct_legal_choices":all_moves,"added_board_keys":added_boards,
        "new_registry":bind(HERE / "known-history-exclusions-v2.json"),"stage":amendment_stage,
        "source":bind(Path(__file__)),"seconds":time.monotonic()-started,
        "calls":{"new_Parquet_rows":0,"new_pairs":0,"new_cohort_selection":0,"model":0,"engine":0,"GPU":0,"network":0},
        "limits":["Exclusion bookkeeping only, not a new quality evaluation or learned result.",
                  "No original game identities inferred or invented for Gotham illustrations.",
                  "The prior metadata-display TypeError about integer versus list rows is retained in the v1 workspace note; no frozen file changed."]}
    assert report["raw_sealed_files_verified_before"] == report["raw_sealed_files_verified_after"]
    assert bind(PRIOR / "FINAL-protocol-PROPOSAL-v1.json") == prior_bindings["protocol"]
    assert bind(PRIOR / "known-history-exclusions.json") == prior_bindings["known_registry"]
    save_new(HERE / "spent-state-amendment-audit-v2.json",report)

    protocol = deepcopy(prior_protocol)
    protocol["schema"] = "chess.matched-check.diagnostic.protocol-proposal.v2"
    protocol["status"] = "FINAL V2 PROPOSAL ONLY: additive spent-state and runtime-proof amendment; not an execution freeze or implementation GO"
    protocol["created_utc"] = datetime.now(timezone.utc).isoformat()
    evidence = protocol["evidence_before_new_work"]
    evidence["known_registry"] = {"path":"work/chess-matched-check-diagnostic-protocol-v2/known-history-exclusions-v2.json",**report["new_registry"]}
    evidence["spent_state_amendment"] = {"path":"work/chess-matched-check-diagnostic-protocol-v2/spent-state-amendment-audit-v2.json",**bind(HERE / "spent-state-amendment-audit-v2.json")}
    evidence["prior_v1_preserved"] = prior_bindings
    evidence["all_frozen_existing_inputs_sha256"].update(new_repo_bindings)
    evidence["additional_workspace_bindings"] = workspace_bindings
    history = protocol["known_history_exclusions"]
    history["stages"]["completed_gotham_first_choices_and_raw_masked_top5_successors"] = amendment_stage
    history["final_known_board_keys"] = 71463
    history["constructed"] = "Immutable constructed preboard and supplied c3h3 fact successor, plus every legal first move and both classifiers' legal raw/masked top5 successors from the completed sealed run24401. Seven distinct legal moves produce six additional board keys; no invented game ID. Original game/history/mainline remain unknown; constructed clocks0/1 are computational. No active raw, fact-label or model-quality score file was read for this amendment."
    runtime = protocol["future_runtime_guards"]
    runtime["owner"] = "Root serializes one new local native job only after source/intake reviews and explicit execution GO. Completed run24401 remains immutable; no current GPU/model work is authorized by this proposal."
    runtime["cpu_intake_maximum_wall_seconds"] = 600
    runtime["cpu_intake_scope"] = "A separate owned CPU-only attempt starts its600s timer before hash/exclusion preflight and includes source scan, pair selection, labels, output freeze and final hashes. A timeout stops only that owned child after bounded cleanup; parent records failed/partial intake and zero model calls. Never relax the row cap, reuse partial acceptance or resume after timeout. This CPU budget does not reset or extend the separately bounded600s inference job."
    runtime["deadline"] = "One600s total inference-job timer starts at wrapper entry BEFORE preflight or model load and includes all64 calls, raw journaling/seal, separate CPU evaluator completion, identity/content finalization and cleanup. No phase/reset extension and no unbounded evaluator wait outside this timer. At deadline latch cooperative stop; after30s terminate only the exact owned child handle, retaining all incomplete/error/not-run outcomes."
    runtime["loading_reuse"] = "Reuse the exact reviewed Gotham sources/local_backends.py FactBackend/native decode plus owned_native.py and their byte-bound reviewed helper snapshots. Any small adapter/64-row runner change receives full source review and fresh finite CPU-only identity/deadline/cleanup/persistence probes before execution. Load selected step512 ONCE, with adapter enabled for all64 calls; no training entrypoint, duplicate loader, baseline pass or optimizer state. Existing45 checks are historical evidence, not proof that a new wrapper works."
    protocol["model_and_generation"]["loaded_identity_proof"] = "File hashes alone prove only retained packages. At actual load verify tied596049920 BF16 base, exact392 adapter tensors/5046272 F32 scalars and byte-equal loaded adapter state per FactBackend. For an unchanged-base claim, explicitly iterate the same primary named_parameters order/names while EXCLUDING any name containing 'lora_', hash name.encode plus each contiguous CPU uint8 parameter bytes as primary did, and require before+after equality to e3af872d3dca520ddbcc6ebd78caf41dccb84203a7835efa7022545db713c008. FactBackend freezes ALL parameters: do NOT reuse primary requires_grad filtering, which would now include LoRA. Any whole-model-state hash must instead be labelled as such and is not the primary base digest. Retain failures; no fabricated base-integrity success from package file checks."
    protocol["proposed_source_test_scope"]["separate_runtime"] = "Root-owned inference-only runner reuses byte-bound Gotham FactBackend, native decode and owned_native helpers after full adaptation review. Selected-only64 calls/load once. No training entrypoint or duplicate weight loader. Add a paired/class file-only evaluator and actual bounded CPU identity/deadline/closure probes for the new wrapper; prior45 checks do not establish this adaptation's integration."
    for section in ("scientific_status","fixed_scope","source","intake_algorithm","files_after_future_intake","evaluation"):
        assert protocol[section] == prior_protocol[section], section
    save_new(HERE / "FINAL-protocol-PROPOSAL-v2.json",protocol)

    def changed_paths(left,right,path=""):
        if isinstance(left,dict) and isinstance(right,dict):
            result=[]
            for k in sorted(set(left)|set(right)):
                if k not in left or k not in right:
                    result.append(path+"/"+k)
                else:
                    result += changed_paths(left[k],right[k],path+"/"+k)
            return result
        return [] if left == right else [path]
    diff = {"schema":"chess.matched-check.protocol-amendment-diff.v2",
            "from_protocol":prior_bindings["protocol"],"to_protocol":bind(HERE / "FINAL-protocol-PROPOSAL-v2.json"),
            "changed_json_paths":changed_paths(prior_protocol,protocol),
            "unchanged_scientific_sections":["scientific_status","fixed_scope","source","intake_algorithm","files_after_future_intake","evaluation"],
            "summary":"Only completed spent-state bindings/union/stage and root-requested CPU/intake/runtime loader/base-digest proof clarifiers. No new selection, prompt, matching, ranking, denominator, metrics or learned results."}
    save_new(HERE / "protocol-amendment-diff-v2.json",diff)
    handoff = {"schema":"chess.matched-check.protocol-proposal-handoff.v2",
               "status":"Await root protocol-first/new-branch GO; no implementation or selection",
               "files":{name:bind(HERE/name) for name in ("FINAL-protocol-PROPOSAL-v2.json","known-history-exclusions-v2.json","spent-state-amendment-audit-v2.json","protocol-amendment-diff-v2.json","amend_spent_states.py")},
               "new_board_keys":6,"known_board_keys":71463,"known_games":30280,
               "v1_unchanged":prior_bindings,"new_cohort_rows":0,"new_model_engine_GPU_calls":0}
    save_new(HERE / "handoff-v2.json",handoff)
    print(json.dumps(handoff,indent=2))


if __name__ == "__main__":
    main()
