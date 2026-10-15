"""Bind a final text-only proposal to the completed metadata inspection."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = ROOT / "work/repos/sports-play-llm-research"


def bind(path):
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return {"bytes":path.stat().st_size,"sha256":digest.hexdigest()}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


metadata = read(HERE / "source-and-exclusion-metadata.json")
original = read(REPO / "experiments/chess-fact-sft-v1/protocol.json")
amendment_v3 = "experiments/chess-fact-sft-v1/launch-and-persistence-amendment-v3.json"
frozen_inputs = dict(metadata["file_bindings_before"])
frozen_inputs[amendment_v3] = bind(REPO / amendment_v3)
for name in ("scripts/chess_fact_sft_supervise.py", "scripts/chess_native_resources.py",
             "scripts/chess_fact_sft_train.py", "scripts/chess_fact_sft_evaluate.py"):
    frozen_inputs[name] = bind(REPO / name)
assert metadata["file_bindings_before"] == metadata["file_bindings_after"]
assert metadata["calls"]["new_cohort_selection"] == 0
assert bind(HERE / "known-history-exclusions.json") == metadata["known_registry"]

protocol = {
    "schema":"chess.matched-check.diagnostic.protocol-proposal.v1",
    "status":"FINAL PROPOSAL ONLY: not an execution freeze; no implementation, new selection or model calls authorized",
    "created_utc":datetime.now(timezone.utc).isoformat(),
    "question":"Does the fixed selected step-512 fact adapter distinguish checking from non-checking legal moves on matched, known-history-disjoint boards, or repeat the observed always-false check response?",
    "motivation":"The completed primary held-out panel had 0/13 true checks identified, despite 242/256 all-eight accuracy. This diagnostic targets that observed class failure without retraining, changing prompts or comparing checkpoints.",
    "scientific_status":{
        "kind":"Exploratory successor diagnostic of a known failure, not an untouched confirmatory test or a new project acceptance gate.",
        "fresh_definition":"Disjoint from the exact KNOWN games and canonical boards reconstructed in the bound registry only. Original Gotham game IDs and unknown upstream pretraining remain unresolved; do not claim full original-game or pretraining independence.",
        "no_strength_inference":"Legal moves are supplied to a fact-reporting model. This cannot establish move-choice quality, strategy, Elo, commentary, sports transfer, a causal mechanism for failure, or automatic promotion.",
        "reporting":"Report the full fixed denominator and complete class confusion, even if results are negative. No ranking or percentage-point improvement against the primary convenience panel."
    },
    "fixed_scope":{
        "seed":4082032,"games":32,"pre_move_boards":32,"moves_each":2,
        "true_checking_cases":32,"true_nonchecking_cases":32,"total_planned_responses":64,
        "conditions":["primary_v3_selected_step512_only"],
        "source_row_cap":200000,"engine_calls":0,"optimizer_updates":0,
        "alternative_checkpoints":0,"prompt_variants":0,"repeat_generations":0
    },
    "evidence_before_new_work":{
        "metadata_report": {"path":"work/chess-matched-check-diagnostic-protocol-v1/source-and-exclusion-metadata.json",**bind(HERE / "source-and-exclusion-metadata.json")},
        "metadata_inspector":{"path":"work/chess-matched-check-diagnostic-protocol-v1/inspect_existing_metadata.py",**bind(HERE / "inspect_existing_metadata.py")},
        "known_registry":{"path":"work/chess-matched-check-diagnostic-protocol-v1/known-history-exclusions.json",**metadata["known_registry"]},
        "metadata_only_operations":"Existing registered puzzles, fact-selected moves, PGNs and immutable known video inputs were reconstructed. Parquet footer/schema and full-source hash were checked; no new Parquet data rows read, pairs enumerated or cohort selected. No network, engine, pretrained or GPU call.",
        "all_frozen_existing_inputs_sha256":frozen_inputs,
        "hash_scope":"Actual streamed local bytes before and after reconstruction. Model weight hashes below are inherited from bound primary protocol/checkpoint manifests; no new model-weight file rehash or load was needed for this proposal. Future execution must verify them before loading."
    },
    "source":{
        **original["acquisition"],
        "new_acquisition":False,"source_reuse_only":True,
        "metadata":metadata["parquet_metadata_only"],
        "applicable_rights":"Reuse the completed primary protocol's pinned public Lichess CC0-1.0 source and retained acquisition metadata. This step performs no new download, terms acceptance or rights expansion.",
        "columns_to_request":["PuzzleId","GameId","FEN","Moves"],
        "format":"GameId is a string; PuzzleId/FEN/Moves are large_string. There is no GameUrl column. Top-level Themes/OpeningTags are not selected; Parquet physical schema uses nested element leaves.",
        "iteration":"ParquetFile.iter_batches(batch_size=4096, columns=[PuzzleId,GameId,FEN,Moves], row_groups=[group], use_threads=False), ascending row group, batch and physical row order. Record zero-based global ordinal/group/in-group indices.",
        "cap_and_completion":"Inspect ordinals 0 through 199999 at most, including all rejected rows. Stop after accepting the 32nd board, or at the cap. No cohort/model execution is permitted on a shortfall. Preserve the attempted intake and rejection trace; no quota relaxation or replacement."
    },
    "known_history_exclusions":{
        "canonical_game_id":"Full-match ([A-Za-z0-9]{8})(?:/(?:white|black))?(?:#[0-9]+)?; retain the case-sensitive first capture and original native GameId. Reject missing/malformed values; do not infer unknown game identities.",
        "canonical_board_key":"Exactly ' '.join(chess.Board(fen).fen().split()[:4]) using pinned python-chess 1.10.0, orthodox valid boards and default legal-en-passant normalization. Omit half/fullmove clocks for duplicate detection; retain the original complete canonical FEN for prompts.",
        "reconstruct_not_count_only":"Before selection, rehash every bound input; reconstruct the existing registry and all added known roles; require exact sorted-game and sorted-board equality with the bound workspace registry, not merely matching counts.",
        "stages":metadata["stages"],
        "final_known_games":30280,"final_known_board_keys":71457,
        "legacy":"24 historical seed games including already-spent retained replay boards; all registered v1/v2/v3/v4 splits and both source-before/setup-after roles reconstructed from the retained 4 MiB prefix. The 24-item legacy broker-derived manifest adds no new game/board beyond this union, but remains hash-bound and checked.",
        "primary":"All 8192 train, 128 development, 256 held-out primary positions: all 8576 games, source-before/setup-after keys, and the rule-constructible successor of every supplied fact move. No model-quality file or label is needed to reconstruct these roles.",
        "earlier_fact_panel":"All 16 earlier fact games, both source roles and their supplied-move successors.",
        "rollout":"All 64 retained PGNs, their initial state and every legal mainline state:4784 known plies. These are designed software stress games, not real-game identity evidence.",
        "video":"All three immutable illustrative preboards, known opening-history states and three displayed-move successors. These old evaluator observations serve only to exclude spent board keys and never enter candidate selection or any model prompt.",
        "constructed":"The immutable constructed middlegame preboard and its supplied c3h3 fact successor. Constructed clocks 0/1 are computational, not observed game history. No current active illustration raw output, label or score was read.",
        "inventory_gate":"At root's eventual intake GO, confirm that no additional spent cohort/game/board has appeared after this proposal. If current illustration execution or another experiment creates newly spent states not covered here, freeze a hash-bound registry amendment before selection; never read an active score file or silently expand after model outputs.",
        "limits":"Known board exclusions do not authenticate unknown video game identities, exclude their unknown full histories, or establish independence from upstream model pretraining."
    },
    "intake_algorithm":{
        "row_validation":"PuzzleId must be a nonempty ASCII alphanumeric string. Parse GameId exactly as above; parse source FEN as a valid orthodox python-chess Board. Reject malformed fields with a source-order trace. Split Moves at most once and parse ONLY its first token as a legal non-null setup move. Never inspect a later source answer token, rating, theme, opening or popularity.",
        "setup":"Keep source_before_fen; push exactly the first setup move; require a valid, nonterminal setup-after board with legal moves. This setup-after board is the pre-move model input. Check game and both source role keys against known history and already accepted new roles.",
        "candidate_moves":"Enumerate legal moves in lexicographic UCI order on that board. Reject promotions, castling and en passant from candidate pairing. Compute immediate capture status, captured-piece type, moving piece and check via board rules only. No engine, source-answer choice, model output or evaluation score.",
        "matched_pairs":"Enumerate every unordered distinct move pair in lexical UCI order. Require the same from_square, moving piece/color, capture boolean and captured-piece type, with exactly one checking and one nonchecking move. Both successors must be valid, distinct, and absent from known and already accepted new keys. Also reject internal collision among source-before, setup-after and the two successor keys.",
        "pair_rank_canonical_payload":"For every eligible pair, payload={seed:4082032,game_id:canonical_game_id,puzzle_id:PuzzleId,fen:setup_after_full_canonical_FEN,moves:sorted([uci1,uci2])}; encode json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8').",
        "pair_rank":"digest=sha256(ASCII('matched-check-pair-v1')+byte(10)+payload_bytes).hexdigest(); choose min((digest,uci1,uci2)). Choice is fixed after legality/exclusion/matching filters and independent of outputs. Do not modify eligibility to obtain favorable model results.",
        "acceptance":"Process rows in physical source order and accept the first eligible pair from each new game until 32. Assign pair_id='mc-pair-'+format(accepted_index,'02d') for index0..31. Within the chosen pair order the two moves lexicographically and give case_id=pair_id+'-'+str(lexical_index) with indices0/1; IDs do not encode true class and are not in the model prompt. Repeated accepted puzzle identity is a hard integrity failure.",
        "global_new_exclusions":"After acceptance add that canonical game and all four role keys to the new-cohort exclusion union. The pre-move board intentionally appears twice in the two input records of its own pair; it may not recur in another pair or collide with any selected successor.",
        "generation_order":"For each opaque case_id compute sha256(ASCII('matched-check-order-v1')+byte(10)+json.dumps({seed:4082032,case_id:case_id},sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')).hexdigest(); sort by (digest,case_id). Keep evaluator labels in this same sealed order without opening them in generation. Do not run all checking cases first or leak label-dependent names.",
        "rejection_accounting":"One terminal trace outcome per scanned source row in this precedence: invalid; known_or_new_game_overlap; source_role_board_overlap; repeated_accepted_puzzle_identity fatal; no_legal_matched_pair_after_all_filters; accepted. Also retain aggregate candidate move/pair filtering counts and exact source locations. Do not double-count a row into the terminal rejection sum.",
        "shortfall":"A source cap shortfall, oracle mismatch, identity conflict, binding drift or output collision seals a failed intake with zero model calls. Do not resume, overwrite, silently drop, or select a replacement after outcomes."
    },
    "files_after_future_intake":{
        "proposed_private_directory":"data/private/chess-matched-check-diagnostic-v1/cohort",
        "input_only":"inputs.json: {schema, rows:[{case_id,fen,selected_uci}]}, exactly64 in frozen generation order; no source, labels, successor boards, outcomes or cohort class in each model row.",
        "separate_labels":"labels.json: {schema, rows:[{case_id,expected:<all eight facts>}]}, matching exact 64 order. Two routes core.expected_facts and core.independent_facts must agree before any call; strict core.parse_facts must accept each target.",
        "metadata":"dataset.json:32 pair records with game/native ID,puzzle ID,source URL/location,source-before FEN,first setup UCI,setup-after FEN,matched UCIs,successor keys,matching attributes,pair/hash/order evidence,rejection/coverage counts. No source answer tail retained.",
        "bindings":"Copy exact protocol and executed intake/core/helper/test source snapshots, bound exclusion inventory and hashes into a create-only directory. Write before-selection intent and source-order trace. Hash all outputs into frozen-data.json. Immutable intent -> dataset files -> frozen-data manifest; no circular self-hash.",
        "independent_gate":"A separate all-row audit reconstructs both source roles, both moves, all four keys, complete pair enumeration/rank, exact source order/first32 eligibility, current known/new exclusions, both oracles, all 64 prompts/targets and native token boundaries. Source answer tails may be poisoned in tests to prove they never influence selection. No model call until root reviews this audit."
    },
    "model_and_generation":{
        "fixed_selected_step":512,
        "selection_manifest":{"path":"data/private/chess-fact-sft-v1/native-run-v3/checkpoint-512/manifest.json","sha256":"f416c9b9b9c2b9ac287b22f456825893cfe364e98f2731b5add711525e9ee8bc"},
        "base":original["model"],
        "adapter_directory":"data/private/chess-fact-sft-v1/native-run-v3/checkpoint-512/adapter",
        "adapter_files_sha256":{
            "adapter_config.json":"fa55f4e49c6184a04f5bd3a3256ef28ced42986b58a3bef780427f4c4654d38a",
            "adapter_model.safetensors":"9d183cdd12024865e4d4c92864e70c32c6dccd605102a42e9ed8da018d947137",
            "README.md":"d018008d43c1c7454c0909dd34efb6aa4be4f128315234fad1bf27f5ee7a096f"},
        "immutable_base_content_digest":"e3af872d3dca520ddbcc6ebd78caf41dccb84203a7835efa7022545db713c008",
        "prompt":"Exactly current hash-bound core.build_prompt(row,'fen_uci_piece_map') and common.native_prompt(tokenizer,row): same complete primary instruction/schema, native template, thinking disabled. Only pre-move FEN, supplied UCI and same-board piece map enter the prompt. No truth, case/game/source ID, successor, source video, output, or explanation.",
        "generation":original["evaluation"]["generation"],
        "token_gate":"Before pretrained load, independently check all 64 native prompts <=1408 tokens and separate-audit targets <=127 JSON+EOS tokens/full sequence<=1536 with exact joint generation prefix, EOS and target round-trip. No truncation, replacement or edited prompt on overflow. Generator sees input lengths only, not label targets.",
        "no_training_or_search":"No optimizer, gradients, new checkpoint selection, baseline condition or prompt/decoding variants. Do not load retained optimizer/training state.",
        "raw_first":"Exactly 64 planned outcomes. Journal every attempted/generated raw token sequence/text/status and immutable source/model/input bindings; seal all raw data before a separate CPU evaluator opens labels. No response retries, partial-field extraction, JSON grammar, output repair or hidden answer rescue."
    },
    "evaluation":{
        "parser":"Exact hash-bound core.parse_facts, common.decode_generated and common.score_sealed strict type/schema/full-denominator semantics; paired/class summary is an additive evaluator only.",
        "primary":"True-check detection correct /32 planned checking moves and correct non-check rejection /32 planned nonchecking moves, side by side.",
        "confusion":"Show TP/FN/FP/TN for strict-schema completed booleans, with unknown predictions, schema failures, truncation, runtime errors and not-run shown separately for each truth class. Those outcomes receive zero correctness without being relabelled as false predictions.",
        "paired":"Both check labels correct within the same matched board /32 planned pairs; any missing/invalid response makes the pair incorrect.",
        "secondary":"Exact-schema valid /64, all-eight exact /64, all-field per-class support/correctness, predicted check-true count and full 64 outcome ledger. If schema-conditional rates appear, keep their smaller denominator visible and secondary.",
        "limits":"The selected panel is deliberately check-balanced and restricted to boards with matched pairs. It cannot estimate natural accuracy, evaluate promotion/castling/en-passant positives or identify why the failure occurs. No null-hypothesis significance claim from this finite descriptive diagnostic."
    },
    "future_runtime_guards":{
        "owner":"Root serializes the eventual one local native job after current run 24401 has finished and released its resources; no GPU work is authorized now.",
        "resource_contract":"Reuse the exact reviewed current native resource/owned-PID/venv identity and Windows status-file persistence policy, with a new job and create-only directory. Do not retry inference after artifact failures or kill by name.",
        "proposed_total_job_wall_seconds":600,"owned_cancel_grace_seconds":30,
        "reserves":"Inherited primary pre-load 10 healthy 1 s samples: physical>=10GiB,commit headroom>=16GiB,GPU free>=13GiB; during physical>=4GiB,commit headroom>=8GiB,GPU free>=1GiB,nominal 1 s samples,gap <= 3 s. Root must approve exact current resource-source hashes and the inference-only wrapper before execution.",
        "deadline":"One total timer begins before preflight/model load and covers 64 calls, raw seal, evaluation/finalization and cleanup; no phase/reset extension. Cooperative stop at safe boundaries, then only exact owned child handle cleanup after 30 s. Retain incomplete tokens and all remaining not-run outcomes.",
        "stopping":"Resource, ownership, counter, deadline, input-binding or artifact failure stops the attempt. Keep partial evidence and no quality conclusion or implicit restart. This is not an instantaneous allocation guarantee."
    },
    "proposed_source_test_scope":{
        "ownership":"Names are proposed; no repository mutation while chess_media owns its frozen branch. Root assigns a new branch and file ownership after protocol approval.",
        "new_intake":"scripts/chess_matched_check_intake.py and tests/test_chess_matched_check_intake.py only for metadata reconstruction, exact matching/ranking/order, create-only freezing and pre-call validation. Reuse unchanged existing core/helpers under their exact source hashes; no edits to original importer, primary protocol/cohort/common or trained weights.",
        "separate_runtime":"Root-owned new inference-only scripts/chess_matched_check_diagnostic.py plus tests. Reuse reviewed native loading/ownership/resources/generation and common strict scoring; do not invoke the training entrypoint. A separate paired/class file-only evaluator may live in this new script or a small helper.",
        "meaningful_tests":[
            "Native GameId suffix cases, malformed IDs/fields, invalid orthodox boards, illegal setup, and proof that poisoned answer tails/ratings/themes cannot alter selection or prompts.",
            "Known-game overlap, both source roles and each selected successor overlap separately; clock-only duplicate normalization; old primary holdout exclusion; accepted-pair cross-collision and repeated puzzle identity.",
            "Small manually known checking/nonchecking fixtures; same-origin/piece/capture matching, excluded promotion/castle/EP, all-candidate enumeration, hash tie-break, first eligible source order, source cap and no-relaxation shortfall.",
            "Exactly32 boards/64 inputs/32+32 truth support, input/label/order identity and no class label in input IDs or prompts; independent oracle disagreement hard failure.",
            "Protocol/source/registry/source-file tamper before and after selection; refusal of existing output/symlink/partial attempt; failed intent retained, no overwrite or implicit resume.",
            "Native prefix/EOS/length gates using pinned tokenizer CPU only; no pretrained forward; generated tokens with multiple JSON objects/fences/prose/duplicate keys/unknown or wrong types score strictly without repair.",
            "Fake 64-outcome examples including invalid schema, truncation, runtime error and not-run prove 32 / 32 / 32 / 64 denominators, separate confusion failures, pair failure, raw seal-before-label access and no response retry.",
            "Actual CPU-only owned-process identity/deadline/cleanup/persistence probes in bounded temp directories; fake resource/model interfaces do not count as real CUDA integration evidence."
        ],
        "required_legacy_checks":"After actual intake implementation, run tests/test_chess_broker_intake.py, tests/test_chess_real_data.py and tests/test_chess_no_forward_packet.py together using the project venv. Preserve missing historical fixture failures exactly; do not claim the current 9 failed / 5 passed / 89 errors historical state has been repaired without evidence.",
        "finite_review":"Bind complete source/tests/results in review units below 30,000 bytes if using the native project review route; do not clip a source file or treat fake tests as real-model evidence. Root independent source/intake/token reviews precede any actual call."
    },
    "required_gates":[
        "Root reads and approves this final proposal and exact known-history inventory; any additional newly spent evidence requires a preselection amendment.",
        "Freeze protocol-first on a new authorized branch after current owner releases it; implement only agreed new files and preserve all primary evidence.",
        "Root reviews exact full source/tests and retained checks before one create-only actual intake.",
        "Independent all-row/exclusion/first-eligible-pair/native-token audit clears; root separately authorizes64 actual local responses under available resources.",
        "Retained raw64 sealed before separate evaluation; independent postrun source/token/scoring/model-integrity/full-denominator audit before any public summary."
    ],
    "actions_so_far":"Workspace-only proposal and metadata research. No new candidate source rows read, pair search, data cohort selection, implementation, repository/Git mutation, training, model/engine/GPU call or new acquisition."
}
destination = HERE / "FINAL-protocol-PROPOSAL-v1.json"
with destination.open("w",encoding="utf-8",newline="\n") as stream:
    stream.write(json.dumps(protocol,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n")
receipt = {"schema":"chess.matched-check.protocol-proposal-handoff.v1",
           "protocol":bind(destination),"metadata_report":bind(HERE / "source-and-exclusion-metadata.json"),
           "known_registry":bind(HERE / "known-history-exclusions.json"),
           "inspector":bind(HERE / "inspect_existing_metadata.py"),
           "proposal_builder":bind(Path(__file__)),"bound_existing_files":len(frozen_inputs),
           "new_selection_or_model_calls":0,"status":"Proposal requires root review; implementation not started"}
with (HERE / "handoff.json").open("w",encoding="utf-8",newline="\n") as stream:
    stream.write(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt,indent=2))
