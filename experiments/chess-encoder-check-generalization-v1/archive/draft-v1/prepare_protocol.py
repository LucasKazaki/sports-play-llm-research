"""Freeze CPU intake from sealed metadata; do not scan/select Parquet rows."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import chess_encoder_check_generalization_v1 as panel


old=panel.head.read(ROOT/'data/private/chess-encoder-check-v1/selection-before-holdout.json')
plan={'schema':'chess.encoder-check-generalization-protocol.v1','stage':'cpu_intake_only_no_model_or_engine_calls',
    'frozen_at':datetime.now(timezone.utc).isoformat(),
    'implementation_sha256':panel.head.sha(ROOT/'scripts/chess_encoder_check_generalization_v1.py'),
    'source':{**panel.binding('data/private/chess-fact-sft-v1/source/lichess-hf-train-00000.parquet'),
        'license':'CC0-1.0','bytes':294920084,
        'upstream':'https://huggingface.co/datasets/Lichess/chess-puzzles/resolve/461725966ea46898ec6481372a6326de3281bfbd/data/train-00000-of-00003.parquet'},
    'source_row_cap':500000,'seed':4082084,'quotas':panel.QUOTAS,'planned_pairs':64,'planned_move_slots':128,
    'allocation_priority':list(panel.STRATA),
    'matching':{'king_mover':'Sameboard, exactsameorigin,piecetype,captureflag,victimtype.',
        'pawn_mover':'Sameboard, exactsameorigin,piecetype,captureflag,victimtype.',
        'double_check':'Sameboard,piecetype,captureflag,victimtype; negative fromaDIFFERENTsame-typepieceinstance.',
        'remaining_discovered_check':'Sameboard,piecetype,captureflag,victimtype; negative fromaDIFFERENTsame-typepieceinstance.'},
    'matching_amendment':'Original unexecutedproposal requiredsameoriginforallstrata, structurallyexcludingordinarynonpawn/nonkingdiscovered-doublecontrasts. AmendedBEFOREanysourceconstruction orlearnedcall, withauthoredlegalfixture; retainoriginalproposal. Thisisnot matched-origin evidence forthe lasttwoallocations.',
    'flags':'Everypositive retains pawn/king/discovered/double flags andcheckers. Allocationking>pawn>double>remainingdiscoveredisexclusive. Neverrelabelapositivebecauseaquotafilled; choosehighestpriorityopencategorythenfrozenseededSHA256pairtie-break.',
    'source_consumption':'OnlyPuzzleId/GameId/FEN/Moves columns, onlyfirstMovessetuptoken; neverparseanswer tail/themes/additionalplies. Validnonterminalorthodoxbefore/current. Onegame/pair andallfourbefore/current/positiveafter/negativeaftercanonicalfirst4FENkeysuniqueandnovelagainstfullregistryandnewpairs.',
    'shortages':'Fixed500ksourceprefix orallquotasfilled; noadaptivematching/cap/quotachange. Persist64plannedpairslots/128moveslots, actualconstructedinputs separately. Unfilledsource_shortageiscoverageunavailable,notmodelerror; neverinventFENs orsilentlydropstrata.',
    'old_head_protocol':panel.binding('experiments/chess-encoder-check-v1/protocol-v2.json'),
    'old_selection':panel.binding('data/private/chess-encoder-check-v1/selection-before-holdout.json'),
    'selected':old['selected'],'original_untrained':old['candidates'][0],
    'expected_reserved_counts':{'games':109032,'board_keys':250895},
    'exclusions':{key:panel.binding(name)for key,name in{
        'coach_reserved':'data/private/chess-queen-coach-sft-v1/reserved-exclusions.json',
        'coach_manifest':'data/private/chess-queen-coach-sft-v1/manifest.json',
        'coach_initial':'data/private/chess-queen-coach-sft-v1/initial-exclusions.json',
        'coach_dataset':'data/private/chess-queen-coach-sft-v1/dataset.json',
        'head_initial':'data/private/chess-encoder-check-v1/initial-exclusions.json',
        'head_dataset':'data/private/chess-encoder-check-v1/dataset.json',
        'head_frozen':'data/private/chess-encoder-check-v1/frozen.json',
        'queen_pool':'data/private/chess-queen-benchmark-v1/dataset.json'}.items()},
    'exclusion_scope':'Verify reservationhash againstcoachmanifest andsupersetsofhead/coachinitialregistries, everyheadroot/selectedsuccessor, all96Queenpoolroots andall1568coachsourcegames/before/current includingall512unusedheldreservoir. Persistedreservedregistryalsocarrieshistoricalteacherpaths. DoNOTopen coach held reference/teachercontents. No claim of excludingfuture generated paths or unregisteredboards.',
    'maximum_cpu_seconds':1200,'cpu_physical_bytes':4*1024**3,'cpu_start_commit_bytes':8*1024**3,'cpu_running_commit_bytes':6*1024**3,
    'resources':'OneCPUprocess, Parquetuse_threadsFalse; hostcountersonly/noGPUquery. Cooperativeread-onlyguardbefore sourcework/every512rows, atmost1Hz. Stopownlaneonreserve/deadline/CANCEL,retainselectedjournal/failure; noGPU/OSchanges.',
    'future_evaluation':'Notenabledbythisprotocol. Requireindependentactualcohortaudit andseparatelyfrozenroot-onlyinferenceplan. Fixedepoch0vsepoch4plusmajorityfalse, noretuning/selection. ExactlyoldcurrentFEN+legalUCI/3072currentfeatures/nativePOVindices; newlabel-freecache. Raw>=0threshold,nomask/rescue. Report perallocation/overlapflag/confusion/recalls/paircorrectness/failedunknownnotrun withactualandrequestedcoverage separately.',
    'limits':'Deliberatelytargetedsmalltactical16pairs/allocation, differingorigincontrastforthelasttwoallocations,unknownencoderpretrainingoverlap. Not prevalence/Elo/movestrength/coachingquality; source shortageisnotmodel failure.',
    'dependencies':[panel.binding(name)for name in[
        'scripts/chess_encoder_check_v1.py','scripts/chess_board_fact_core.py',
        'scripts/chess_check_balanced_v2.py','scripts/chess_fact_sft_intake.py','scripts/chess_fact_sft_common.py',
        'scripts/chess_queen_materialize.py','tests/test_chess_encoder_check_generalization_v1.py']]}
audit=panel.exclusions(plan)
preflight={'status':'metadata_only_passed','reserved_superset_audit':audit[2],
    'source_rows_constructed':0,'model_calls':0,'engine_calls':0,'coach_held_reference_reads':0}
with(HERE/'exclusion-preflight.json').open('x',encoding='utf-8')as stream:json.dump(preflight,stream,indent=2);stream.write('\n')
plan['dependencies'].append(panel.binding('experiments/chess-encoder-check-generalization-v1/exclusion-preflight.json'))
with(HERE/'protocol.json').open('x',encoding='utf-8')as stream:json.dump(plan,stream,indent=2);stream.write('\n')
panel.verify(HERE/'protocol.json')
print(json.dumps({'protocol':panel.binding('experiments/chess-encoder-check-generalization-v1/protocol.json'),'audit':preflight}))
