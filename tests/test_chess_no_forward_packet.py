"""Real dev inputs; adversarial software controls, not generated explanations."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import chess
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import chess_counterfactual_evidence as cf
import chess_typed_position_evidence as adapter
import chess_no_forward_packet as nf

DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'
SOURCE = ROOT / 'artifacts/chess-counterfactual-v1/dev8-node100k-v3.json'
TYPED = ROOT / 'artifacts/chess-typed-position-evidence-v1/dev8-adapter-v1.json'
SHA = 'a4a7e47533797e2cc08ca6d2fdefedfe2cb008d09f6bf1056d6aa421630f03e6'
FORBIDDEN = ('pv_uci', 'pv_final_fen', 'fen_after', 'post_move_fen', 'future_moves',
             'solution', 'themes', 'answer_label', 'annotations', 'reply_sequence',
             'future_board_feature', 'score_info_sequence', 'commentary_evidence')


@pytest.fixture(scope='module')
def typed():
    return adapter.build_typed_position_evidence(DATA, SOURCE, SHA)


def inputs(typed, row=None, candidate=None):
    row = row or typed['positions'][0]
    candidate = candidate or row['engine_evidence'][0]
    return (DATA, SOURCE, SHA, typed, row['position_id'], candidate['evidence_id'])


@pytest.fixture(scope='module')
def packet(typed):
    return nf.build_no_forward_packet(*inputs(typed))


def test_every_real_candidate_has_only_pre_move_and_selected_transition_inputs(typed):
    seen = 0
    before = cf.canonical(typed)
    for row in typed['positions']:
        for candidate in row['engine_evidence']:
            args = inputs(typed, row, candidate)
            packet = nf.build_no_forward_packet(*args)
            encoded = nf.encode_no_forward_packet(*args, packet)
            board = chess.Board(row['fen']); move = chess.Move.from_uci(candidate['move_uci'])
            assert move in board.legal_moves
            assert packet['fen'] == row['fen']
            assert packet['side_to_move'] == chess.COLOR_NAMES[board.turn]
            assert packet['selected_move'] == {'uci': move.uci(), 'san': board.san(move)}
            assert packet['transition']['capture'] == board.is_capture(move)
            assert packet['transition']['gives_check'] == board.gives_check(move)
            assert packet['engine_observation']['score'] == candidate['score']
            assert packet['source']['split'] == 'dev'
            assert packet['source']['typed_packet_sha256'] == cf.digest(before)
            for forbidden in FORBIDDEN:
                assert ('"' + forbidden + '"').encode() not in encoded
            assert candidate['pv_final_fen'].encode() not in encoded
            assert candidate['transition']['fen_after'].encode() not in encoded
            assert len(encoded) <= 16384
            seen += 1
    assert seen == 16 and cf.canonical(typed) == before


@pytest.mark.parametrize('field', FORBIDDEN)
def test_prohibited_fields_at_any_object_depth_never_reach_generator(typed, packet, field):
    for path in ((), ('source',), ('selected_move',), ('transition',),
                 ('engine_observation',), ('engine_observation', 'score')):
        changed = copy.deepcopy(packet); target = changed
        for key in path: target = target[key]
        target[field] = ['e7e5', 'future-answer-control']
        calls = []
        with pytest.raises(ValueError, match='no_forward_'):
            nf.dispatch_no_forward(*inputs(typed), changed, lambda raw: calls.append(raw))
        assert calls == []


@pytest.mark.parametrize('path,value', [
    (('fen',), chess.STARTING_FEN), (('side_to_move',), 'white'),
    (('selected_move', 'uci'), 'e2e5'), (('selected_move', 'san'), 'forced win'),
    (('transition', 'capture'), 0), (('transition', 'moving_piece'), 'queen'),
    (('transition', 'gives_check'), {'future_annotation': 'mate soon'}),
    (('source', 'url'), 'https://example.invalid/annotation'),
    (('source', 'split'), 'test'), (('source', 'receipt_sha256'), '0' * 64),
    (('source', 'typed_packet_sha256'), '0' * 64),
    (('engine_observation', 'evidence_id'), 'foreign'),
    (('engine_observation', 'engine_sha256'), '0' * 64),
    (('engine_observation', 'independently_reproduced'), True),
    (('engine_observation', 'score', 'value'), 663.0),
    (('engine_observation', 'score', 'bound'), 'lower'),
    (('engine_observation', 'score', 'perspective'), 'white'),
    (('concept_vocabulary',), ['solution-mate']),
    (('assertion_kinds',), ['professional_teaching']),
])
def test_allowed_field_tampering_is_also_rejected_before_dispatch(typed, packet, path, value):
    changed = copy.deepcopy(packet); target = changed
    for key in path[:-1]: target = target[key]
    assert target[path[-1]] != value or type(target[path[-1]]) is not type(value)
    target[path[-1]] = value; calls = []
    with pytest.raises(ValueError):
        nf.dispatch_no_forward(*inputs(typed), changed, lambda raw: calls.append(raw))
    assert not calls


@pytest.mark.parametrize('changed', [None, [], {}, 'confident annotation', {'schema': nf.SCHEMA}])
def test_bad_root_shapes_never_dispatch(typed, changed):
    calls = []
    with pytest.raises(ValueError):
        nf.dispatch_no_forward(*inputs(typed), changed, lambda raw: calls.append(raw))
    assert not calls


def test_missing_unknown_and_legacy_whole_packets_fail_closed(typed, packet):
    for changed in (typed, typed['positions'][0], {**packet, 'unrecognized_extension': {}},
                    {k: v for k, v in packet.items() if k != 'transition'}):
        with pytest.raises(ValueError): nf.encode_no_forward_packet(*inputs(typed), changed)


def test_candidate_and_position_reference_cannot_be_swapped(typed, packet):
    row = typed['positions'][0]
    for position, evidence in (('absent', row['engine_evidence'][0]['evidence_id']),
                               (row['position_id'], typed['positions'][1]['engine_evidence'][0]['evidence_id']),
                               (row['position_id'], row['engine_evidence'][1]['evidence_id']), (None, 1)):
        with pytest.raises(ValueError):
            nf.encode_no_forward_packet(DATA, SOURCE, SHA, typed, position, evidence, packet)


def test_changed_source_or_evaluator_packet_never_dispatches(typed, packet, tmp_path):
    changed_source = tmp_path / 'changed-source.json'; changed_source.write_bytes(SOURCE.read_bytes() + b'\n')
    changed_typed = copy.deepcopy(typed)
    changed_typed['positions'][0]['engine_evidence'][0]['pv_uci'] = ['e2e4']
    calls = []
    for source, evidence in ((changed_source, typed), (SOURCE, changed_typed)):
        with pytest.raises(ValueError, match='pinned_source'):
            nf.dispatch_no_forward(DATA, source, SHA, evidence, *inputs(typed)[4:], packet,
                                    lambda raw: calls.append(raw))
    assert not calls


def test_dispatch_has_one_canonical_argument_and_preserves_raw_output(typed, packet, monkeypatch):
    calls = []; original = cf.canonical(packet)
    def engine_forbidden(*args, **kwargs): raise AssertionError('No new engine execution')
    monkeypatch.setattr(chess.engine.SimpleEngine, 'popen_uci', engine_forbidden)
    raw_response = 'MALFORMED RAW OUTPUT: not an accepted explanation'
    def generate(*args):
        assert len(args) == 1 and type(args[0]) is bytes
        calls.append(args[0]); return raw_response
    result = nf.dispatch_no_forward(*inputs(typed), packet, generate)
    assert result == raw_response and calls == [original]
    assert cf.canonical(packet) == original


def test_transport_failure_is_not_retried_or_replaced(typed, packet):
    calls = []
    def generate(raw): calls.append(raw); raise OSError('synthetic local transport failure')
    with pytest.raises(OSError, match='synthetic'):
        nf.dispatch_no_forward(*inputs(typed), packet, generate)
    assert len(calls) == 1


@pytest.mark.parametrize('kind,value,bound,zero', [
    ('cp', -53, 'lower', None), ('cp', 22, 'upper', None),
    ('mate', 3, 'exact', None), ('mate', -2, 'exact', None),
    ('mate', 0, 'exact', 'delivered'), ('mate', 0, 'exact', 'received'),
])
def test_synthetic_score_types_keep_perspective_bounds_and_mate_zero(typed, monkeypatch,
                                                                  kind, value, bound, zero):
    # A software-only shape probe; it is not an actual engine observation.
    fixture = copy.deepcopy(typed)
    score = fixture['positions'][0]['engine_evidence'][0]['score']
    score.update(type=kind, value=value, bound=bound)
    if zero is not None: score['mate_zero'] = zero
    monkeypatch.setattr(adapter, 'validate_typed_position_evidence', lambda *args: None)
    packet = nf.build_no_forward_packet(*inputs(fixture))
    assert packet['engine_observation']['score'] == score
    assert packet['engine_observation']['score']['perspective'] == 'side_to_move'
    assert packet['engine_observation']['observation_only'] is True
    assert packet['engine_observation']['independently_reproduced'] is False


def test_cli_build_verify_and_no_overwrite(typed, tmp_path):
    output = tmp_path / 'packet.json'; args = inputs(typed)
    tail = ['--data', str(DATA), '--source', str(SOURCE), '--source-sha256', SHA,
            '--typed-packet', str(TYPED), '--position-id', args[4], '--evidence-id', args[5],
            '--output', str(output)]
    def run(command):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/chess_no_forward_packet.py'), command, *tail],
                              text=True, capture_output=True, timeout=30, cwd=ROOT)
    built = run('build'); assert built.returncode == 0, built.stderr
    original = output.read_bytes(); first = json.loads(built.stdout)
    assert first['packet_sha256'] == cf.digest(original) and first['model_calls'] == 0
    verified = run('verify'); assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout) == first
    assert run('build').returncode != 0 and output.read_bytes() == original
    changed = json.loads(original); changed['annotations'] = ['synthetic future answer']
    output.write_bytes(cf.canonical(changed)); assert run('verify').returncode != 0
