"""Metadata-only freeze for the new CC0 paired curriculum. No data construction."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def bind(path):
    path=Path(path);path=path if path.is_absolute()else ROOT/path
    return {'path':str(path.relative_to(ROOT))if path.is_relative_to(ROOT)else str(path),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    gen=json.loads((ROOT/'experiments/chess-encoder-check-generalization-v1/protocol-v2.json').read_text())
    coach=json.loads((ROOT/'experiments/chess-queen-coach-sft-v1/protocol-v3.json').read_text())
    names=[item['path']for item in gen['dependencies']+coach['dependencies']]
    names += ['scripts/chess_encoder_check_generalization_v1.py','scripts/chess_queen_coach_sft_intake_v1.py',
        'scripts/chess_queen_coach_counterfactual_intake_v1.py','scripts/chess_queen_coach_counterfactual_teacher_v1.py',
        'tests/test_chess_queen_coach_counterfactual_intake_v1.py','tests/test_chess_queen_coach_counterfactual_teacher_v1.py',
        '.venv-soccernet/Lib/site-packages/chess/engine.py',str(Path(__file__))]
    registry='data/private/chess-encoder-check-generalization-v1/reserved-exclusions.json'
    plan={'schema':'chess.queen-coach-counterfactual-intake.v1','frozen_at':datetime.now(timezone.utc).isoformat(),
        'implementation_sha256':bind('scripts/chess_queen_coach_counterfactual_intake_v1.py')['sha256'],
        'teacher_implementation':bind('scripts/chess_queen_coach_counterfactual_teacher_v1.py'),
        'counts':{'train':512,'development':32,'reserve':512},'seed':4082085,'source_row_cap':500000,
        'source':{**bind(gen['source']['path']),'license':'CC0-1.0','publisher_revision':'461725966ea46898ec6481372a6326de3281bfbd'},
        'registry':bind(registry),'registry_counts':{'games':109096,'board_keys':251151},
        'generalization_protocol':bind('experiments/chess-encoder-check-generalization-v1/protocol-v2.json'),
        'generalization_dataset':bind('data/private/chess-encoder-check-generalization-v1/dataset.json'),
        'generalization_closed':bind('data/private/chess-encoder-check-generalization-v1/closed.json'),
        'teacher':{'binary':bind(coach['teacher']['binary']['path']),'workers':1,'threads':1,'hash_mb':32,'nodes':50000,
            'request_maximum_seconds':30,'phase_maximum_seconds':3300,'api':'SimpleEngine.analysis(root_moves=[selectedMove]) for supplied cases; root_moves=None for FREE. UCI emits searchmoves; unique game token per request.'},
        'maximum_cpu_seconds':1200,'cpu_start_commit_bytes':8*1024**3,'cpu_running_commit_bytes':6*1024**3,
        'cpu_physical_bytes':4*1024**3,'cutoff_utc':'2026-10-16T13:00:00+00:00',
        'source_contract':'First setup token only; valid/nonterminal before AND current, exact first6FEN input. One original game/root. No source solution/themes/tail read or use. Fixed500000 source prefix; exact512/32/512 or insufficient_cohort, no adaptive extension/replacement.',
        'split':'SHA256(counterfactual-coach-v1:4082085:<canonical game>) modulo16:0..7 TRAIN,8development,9..15reserve; first eligible source order.',
        'matching':'Same board, pieceTYPE,captureflag,victimtype. Prefer exactsameorigin pair if any exist; otherwise other same-type instance. Seeded SHA pair tie; no promotion/castling/EP, piece/capture quotas or later relaxation. Keep origin/overlap flags reference-only.',
        'identity':'Opaque free/selected_a/selected_b IDs and modes; a/b assigned by seeded SHA of game+UCI without check labels. FREE input exactly{fen}; supplied input exactly{fen,selected_uci}. No labels/checkrole/stratum/postboard/PV/evaluation enters input or any learned feature cache.',
        'reservation':'Exclude the entire109096game/251151board registry before/current/both immediate successors. Superset audit includes all oldcoach512 reserve and all newgeneralization64 games/256roles. Teacher paths checked for TRAIN-to-dev AND TRAIN/dev-to-reserve collision; any collision fails the cohort, no replacement. Historical teacher-tail overlap reported separately; no unregistered future-path novelty claim.',
        'teacher_proof':'Exactly3168planned requests persisted before setup; fsynced per-call intent and raw incomingUCI/outcome. Last individual same-event score/PV must match finalbest; forced final must equal selected. Preserve scorebounds, legal replay<=3 stops before automaticterminal. First backend/timeout/resource/cancel failure stops ALL later requests; unknown vsnotrun retained, no retry.',
        'targets':'Retain oneFREEunrestrictedbest and two balanced legal supplied-move targets/root. Exact native verified check/mate +capture/no-capture; BEST and<=3CRITICAL only OUTPUT. Supplied BEST under singletonconstraint, not globalbest; supplied PROMISING empty, evaluationNotassessed except immediate ruleterminal. No generic strategic why-best or unsupported alternatives.',
        'export_gates':'All3168complete and exact task identities; independent replay onecheck+onenoncheck and piece/capture/victim match. All512reserve eligibility rows kept; first16sourceorder roots with all3references supporting3legal nonterminal-before-each plies and historical/TRAIN/dev path novelty. First2full3ply devroots; fail shortage, no replacements. Full TRAIN1536/dev96/held48examples percondition, all512games+allteacherpaths remain reserved.',
        'future_model_boundary':'CPU only here. Separate frozen reviewed training/held protocol required. Fixed oldselected64 baseline/warmstart, same CE/architecture,192updates,96heldcalls. Latest dispatch11:15UTC for EACH new GPU phase, global13UTC; no quota/deadline shrink. RootsoleGPUdispatcher, no currentcoachheld reference reads.',
        'joint_fact_contract':'Completed EOS; exactlyone accepted BEST equal supplied; exactlyone unambiguous recognized ANALYSIS move equal supplied; complete true check+capture claims. Contradictions/duplicates/mismatched/unrecognized ANALYSIS cannot jointsuccess. Preserve every recognized span/count separately; unknown prose remains unaudited.',
        'dependencies':[bind(name)for name in dict.fromkeys(names)]}
    target=HERE/'intake-protocol.json'
    if target.exists():raise ValueError('Freeze is create-only')
    target.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'protocol':bind(target),'intake':bind('scripts/chess_queen_coach_counterfactual_intake_v1.py'),
        'teacher':plan['teacher_implementation']}))


if __name__=='__main__':main()
