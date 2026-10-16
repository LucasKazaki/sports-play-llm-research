"""CPU software fixtures; no pretrained encoder, source cohort or GPU calls."""
import json
from pathlib import Path
import sys

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import chess_encoder_check_v1 as experiment

FEN = '6k1/8/8/8/8/8/R7/6K1 w - - 0 1'


def pair(fen=FEN, prefix='first'):
    return [{'case_id': prefix + '-yes', 'fen': fen, 'selected_uci': 'a2a8'},
            {'case_id': prefix + '-no', 'fen': fen, 'selected_uci': 'a2b2'}]


def labels(rows):
    return [{'case_id': row['case_id'], 'gives_check': row['case_id'].endswith('yes')} for row in rows]


@pytest.mark.parametrize('extra', ['reference_pv', 'post_fen', 'gives_check', 'history', 'selected_san', 'solution'])
def test_inference_boundary_rejects_future_and_answer_fields(extra):
    with pytest.raises(ValueError):
        experiment.packet({'fen': FEN, 'selected_uci': 'a2a8', extra: 'forbidden'})


def test_selected_move_must_be_legal_on_valid_nonterminal_current_board():
    with pytest.raises(ValueError):
        experiment.packet({'fen': FEN, 'selected_uci': 'a2b3'})
    terminal = '7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'
    with pytest.raises(ValueError):
        experiment.packet({'fen': terminal, 'selected_uci': 'h8h7'})


def test_black_native_square_indices_and_promotion_class_are_explicit():
    white = {'fen': FEN, 'selected_uci': 'a2a8'}
    black = {'fen': chess.Board(FEN).mirror().fen(), 'selected_uci': 'a7a1'}
    assert experiment.move_indices(white) == experiment.move_indices(black) == (8, 56, 0)
    promotion = {'fen': '7k/P7/8/8/8/8/8/7K w - - 0 1', 'selected_uci': 'a7a8n'}
    assert experiment.move_indices(promotion) == (48, 56, 1)


def test_same_current_fen_is_encoded_once_but_every_requested_move_has_identity():
    rows = pair() + pair(FEN.replace('0 1', '1 1'), 'second')
    groups = experiment.requests(rows)
    assert len(groups) == 2 and [len(group) for _, group in groups] == [2, 2]
    assert groups[0][1][0]['input_sha256'] != groups[0][1][1]['input_sha256']
    with pytest.raises(ValueError, match='Duplicate'):
        experiment.requests(rows + [rows[0]])
    with pytest.raises(ValueError):
        experiment.requests([{**rows[0], 'gives_check': True}])


def test_features_are_current_state_mean_source_target_in_native_pov_order():
    torch = pytest.importorskip('torch')
    state = torch.arange(64, dtype=torch.float32).reshape(1, 64, 1).expand(2, -1, 1024)
    values = [{'fen': FEN, 'selected_uci': 'a2a8'},
              {'fen': chess.Board(FEN).mirror().fen(), 'selected_uci': 'a7a1'}]
    features = experiment.compact_features(state, values)
    assert features.shape == (2, 3072)
    assert torch.equal(features[0], features[1])
    assert features[0, 0].item() == 31.5
    assert features[0, 1024].item() == 8
    assert features[0, 2048].item() == 56
    with pytest.raises(ValueError, match='Nonfinite'):
        experiment.compact_features(state.clone().fill_(float('nan')), values)


def test_real_gradient_path_updates_only_the_new_head_on_synthetic_features():
    torch = pytest.importorskip('torch')
    torch.manual_seed(12)
    head = experiment.make_head()
    features = torch.randn(4, 3072)
    indices = torch.tensor([[0, 1, 0], [0, 2, 0], [3, 4, 0], [3, 5, 0]])
    targets = torch.tensor([1., 0., 1., 0.])
    optimizer = torch.optim.AdamW(head.parameters(), lr=.001)
    first = torch.nn.functional.binary_cross_entropy_with_logits(head(features, indices), targets)
    optimizer.zero_grad(); first.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in head.parameters())
    optimizer.step()
    after = torch.nn.functional.binary_cross_entropy_with_logits(head(features, indices), targets)
    assert after.detach() < first.detach()
    assert not features.requires_grad
    assert sum(p.numel() for p in head.parameters()) == 1680169


def test_first_encoder_failure_preserves_every_request_and_stops_later_backend_calls():
    groups = experiment.requests(pair() + pair(FEN.replace('0 1', '1 1'), 'second'))
    calls, attempts = [], []
    def broken(fen):
        calls.append(fen)
        raise RuntimeError('backend failed')
    ledger, error = experiment.extract_groups(groups, broken, lambda *args: [], lambda *args: attempts.append(args))
    assert len(calls) == len(attempts) == 1
    assert [r['status'] for r in ledger] == ['failed', 'failed', 'not_run', 'not_run']
    assert len(ledger) == 4 and 'backend failed' in error


def test_first_head_failure_keeps_failed_batch_and_remaining_pairs_without_retry():
    torch = pytest.importorskip('torch')
    rows = pair() + pair(FEN.replace('0 1', '1 1'), 'second')
    class Broken(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.calls = 0
        def forward(self, x, moves):
            self.calls += 1
            raise RuntimeError('first failed head call')
    head = Broken()
    raw, scored, error = experiment.evaluate_head(head, rows, labels(rows), torch.zeros(4, 3072),
        torch.zeros(4, 3, dtype=torch.long), 2, lambda: None, device='cpu')
    assert head.calls == 1 and error
    assert [r['status'] for r in raw] == ['failed', 'failed', 'not_run', 'not_run']
    assert scored['planned'] == 4 and scored['pairs_planned'] == 2 and scored['correct'] == 0
    assert scored['confusion']['invalid_positive'] == scored['confusion']['invalid_negative'] == 2
    assert scored['confusion']['tn'] == scored['confusion']['fn'] == 0


def test_raw_zero_logit_threshold_has_no_class_mask_or_label_replacement():
    torch = pytest.importorskip('torch')
    rows = pair()
    class Zero(torch.nn.Module):
        def forward(self, x, moves):
            return torch.zeros(len(x))
    raw, scored, error = experiment.evaluate_head(Zero(), rows, labels(rows), torch.zeros(2, 3072),
        torch.zeros(2, 3, dtype=torch.long), 2, lambda: None, device='cpu')
    assert error is None and [r['prediction'] for r in raw] == [True, True]
    assert scored['confusion']['tp'] == scored['confusion']['fp'] == 1
    assert scored['pairs_correct'] == 0


def test_selector_prefers_correct_then_pair_correct_then_earliest_including_baseline():
    candidates = [dict(epoch=0, correct=250, pairs_correct=120), dict(epoch=1, correct=251, pairs_correct=120),
                  dict(epoch=2, correct=251, pairs_correct=121), dict(epoch=4, correct=251, pairs_correct=121)]
    assert max(candidates, key=experiment.selection_key)['epoch'] == 2
    candidates[0].update(correct=251, pairs_correct=121)
    assert max(candidates, key=experiment.selection_key)['epoch'] == 0


def test_majority_false_and_invalid_predictions_use_complete_balanced_denominator():
    rows = pair()
    raw = [{'case_id': r['case_id'], 'status': 'completed', 'prediction': False} for r in rows]
    scored = experiment.score(rows, labels(rows), raw)
    assert scored['planned'] == 2 and scored['correct'] == 1 and scored['pairs_correct'] == 0
    assert scored['checking_recall'] == 0 and scored['nonchecking_recall'] == 1
    with pytest.raises(ValueError, match='every planned'):
        experiment.score(rows, labels(rows), raw[:1])


def source(game='test0001', puzzle='fixture1', before=None, ordinal=0):
    return {'source_ordinal': ordinal, 'parquet_row_group': 0, 'parquet_row_in_group': ordinal}, {
        'GameId': game, 'PuzzleId': puzzle, 'FEN': before or FEN.replace(' w ', ' b '),
        'Moves': 'g8h8 POISON_SOLUTION_TAIL', 'Themes': 'POISON_THEME'}


def test_fresh_holdout_consumes_setup_only_and_keeps_both_balanced_inputs_and_source_roles():
    inputs, truth, metadata, rejected = experiment.select_holdout([source()], set(), set(), 1, 33, 10)
    assert len(inputs) == len(truth) == 2 and len(metadata) == 1
    assert sum(row['gives_check'] for row in truth) == 1
    assert all(set(row) == {'case_id', 'fen', 'selected_uci'} for row in inputs)
    assert 'POISON' not in json.dumps([inputs, truth, metadata])
    assert metadata[0]['source_before_fen'] != metadata[0]['fen']
    assert metadata[0]['setup_uci'] == 'g8h8'


def test_source_game_and_before_board_exclusions_are_applied_before_new_pair_selection():
    with pytest.raises(ValueError, match='cannot fill'):
        experiment.select_holdout([source()], {'test0001'}, set(), 1, 33, 10)
    before = source()[1]['FEN']
    with pytest.raises(ValueError, match='cannot fill'):
        experiment.select_holdout([source()], set(), {experiment.board_key(before)}, 1, 33, 10)


def test_all_v6_reservoir_rows_remain_in_exclusions_including_unused_candidates(tmp_path, monkeypatch):
    cohort = tmp_path / 'v6.json'; registry = tmp_path / 'registry.json'; queen = tmp_path / 'queen.json'
    before = FEN.replace(' w ', ' b ')
    cohort.write_text(json.dumps({'new_splits': {'train': [{'game_id': 'test0001', 'fen': FEN}],
        'rollout': [{'game_id': 'test0002', 'source_before_fen': before, 'fen': FEN.replace('0 1', '1 1')} ]}}))
    registry.write_text(json.dumps({'games': ['old00001'], 'board_keys': []}))
    queen.write_text(json.dumps({'splits': {'development': [{'game_id': 'queen001', 'fen': FEN}],
        'holdout': [{'game_id': 'queen002', 'fen': before}]}}))
    monkeypatch.setattr(experiment, 'bound', lambda item: Path(item['path']))
    games, boards = experiment.exclusions({'known_registry': {'path': str(registry)},
        'excluded_cohorts': [{'path': str(cohort)}], 'queen_benchmark': {'path': str(queen)}})
    assert games == {'old00001', 'test0001', 'test0002', 'queen001', 'queen002'}
    assert experiment.board_key(before) in boards and experiment.board_key(FEN) in boards


def test_reused_pair_labels_must_remain_complete_ordered_and_balanced():
    rows = pair()
    with pytest.raises(ValueError, match='order'):
        experiment.validate_labels(rows, list(reversed(labels(rows))))
    with pytest.raises(ValueError, match='exactly one'):
        experiment.validate_labels(rows, [{'case_id': r['case_id'], 'gives_check': False} for r in rows])


def test_stale_cohort_protocol_stops_before_any_feature_directory_or_model_call(tmp_path, monkeypatch):
    protocol = tmp_path / 'protocol.json'; protocol.write_text('{}')
    out = tmp_path / 'cohort'; out.mkdir()
    (out / 'frozen.json').write_text(json.dumps({'protocol_sha256': 'old-protocol'}))
    monkeypatch.setattr(experiment, 'verify', lambda path: {})
    with pytest.raises(ValueError, match='Cohort and execution'):
        experiment.features(protocol, out, 'training')
    assert not (out / 'features-training').exists()


def test_feature_cache_input_hash_and_shard_bytes_are_verified_before_head_use(tmp_path):
    torch = pytest.importorskip('torch')
    rows = pair(); truth = labels(rows)
    protocol = tmp_path / 'protocol.json'; protocol.write_text('{}')
    experiment.save(tmp_path / 'train-inputs.json', {'rows': rows})
    experiment.save(tmp_path / 'train-labels.json', {'rows': truth})
    experiment.save(tmp_path / 'frozen.json', {'files_sha256': {name: experiment.sha(tmp_path / name)
        for name in ('train-inputs.json', 'train-labels.json')}})
    cache = tmp_path / 'features-training'; cache.mkdir()
    shard = cache / 'features.pt'
    torch.save({'features': torch.zeros(2, 3072), 'indices': torch.tensor([
        experiment.move_indices({'fen': row['fen'], 'selected_uci': row['selected_uci']}) for row in rows])}, shard)
    manifest = {'protocol_sha256': experiment.sha(protocol),
        'input_files_sha256': {'train': experiment.sha(tmp_path / 'train-inputs.json')},
        'records': [{'case_id': row['case_id'], 'status': 'completed', 'row': index, 'shard': shard.name,
                     'shard_sha256': experiment.sha(shard), 'input_sha256': experiment.json_hash(
                         experiment.packet({'fen': row['fen'], 'selected_uci': row['selected_uci']}))}
                    for index, row in enumerate(rows)]}
    experiment.save(cache / 'manifest.json', manifest)
    assert experiment.cached_panel(protocol, tmp_path, 'train')[2].shape == (2, 3072)
    shard.write_bytes(b'altered after extraction')
    with pytest.raises(ValueError, match='shard changed'):
        experiment.cached_panel(protocol, tmp_path, 'train')


def test_interrupted_head_batch_preserves_completed_unknown_and_not_run_requests(tmp_path):
    torch = pytest.importorskip('torch')
    rows = pair() + pair(FEN.replace('0 1', '1 1'), 'second') + pair(FEN.replace('0 1', '2 1'), 'third')
    class Interrupted(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.calls = 0
        def forward(self, x, indices):
            self.calls += 1
            if self.calls == 2:
                raise KeyboardInterrupt('simulated interruption after intent')
            return torch.zeros(len(x))
    path = tmp_path / 'condition.json'
    with pytest.raises(KeyboardInterrupt):
        experiment.recorded_evaluate(path, Interrupted(), rows, labels(rows), torch.zeros(6, 3072),
            torch.zeros(6, 3, dtype=torch.long), 2, lambda: None, device='cpu')
    value = experiment.read(path)
    assert [r['status'] for r in value['raw']] == ['completed', 'completed',
        'unknown_after_interruption', 'unknown_after_interruption', 'not_run', 'not_run']
    assert value['score']['planned'] == 6 and value['score']['pairs_planned'] == 3
    journal = path.with_suffix('.attempts.jsonl')
    assert experiment.recover_predictions(rows, journal) == value['raw']
    with journal.open('a') as stream:
        stream.write('{"torn_final_append":')
    assert experiment.recover_predictions(rows, journal) == value['raw']


@pytest.mark.parametrize('setup_failure', ['cache', 'resource'])
def test_both_full_condition_ledgers_exist_before_any_failing_cache_or_guard_setup(tmp_path, monkeypatch, setup_failure):
    rows = pair(); truth = labels(rows)
    protocol = tmp_path / 'protocol.json'; protocol.write_text('{}')
    candidate = {'epoch': 0, 'path': 'not-loaded', 'sha256': 'not-loaded'}
    experiment.save(tmp_path / 'selection-before-holdout.json', {'protocol_sha256': experiment.sha(protocol),
        'candidates': [candidate], 'selected': candidate})
    monkeypatch.setattr(experiment, 'verify', lambda p: {'maximum_seconds': 10, 'training': {'batch_size': 2}})
    monkeypatch.setattr(experiment, 'check_cohort', lambda *args: None)
    monkeypatch.setattr(experiment, 'panel', lambda *args: (rows, truth))
    monkeypatch.setattr(experiment, 'snapshot', lambda *args: None)
    def fail(*args):
        raise RuntimeError('deliberate setup failure')
    monkeypatch.setattr(experiment, 'cached_panel', fail if setup_failure == 'cache' else lambda *args: (rows, truth, None, None))
    monkeypatch.setattr(experiment, 'guard_for', lambda *args: fail)
    with pytest.raises(RuntimeError, match='setup failure'):
        experiment.evaluate(protocol, tmp_path)
    for condition in ('untrained_head', 'selected_head'):
        value = experiment.read(tmp_path / 'evaluation' / (condition + '.json'))
        assert value['score']['planned'] == 2 and value['score']['pairs_planned'] == 1
        assert value['score']['statuses'] == {'not_run': 2}
