"""Boundary, strict scoring and exact-child timing tests; no pretrained calls."""
import copy
import json
from pathlib import Path
import sys
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import chess_board_fact_core as core
from chess_fact_sft_common import (native_prompt, native_training_row, collate_training,
    decode_generated, seal_raw, score_sealed, select_checkpoint, read, save, sha,
    declare_run, finalize_run_ledger)
from chess_fact_sft_supervise import phase_deadline, termination_due

FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
ROW = {'case_id': 'fixture', 'fen': FEN, 'selected_uci': 'e2e4'}


@pytest.fixture(scope='module')
def tokenizer():
    from transformers import AutoTokenizer
    path = SCRIPTS.parent/'data/private/chess-fact-sft-v1/models/base'
    return AutoTokenizer.from_pretrained(path, trust_remote_code=False, local_files_only=True)


def test_native_boundary_uses_assistant_eos_not_user_eos(tokenizer):
    truth = core.expected_facts(FEN, 'e2e4')
    row = native_training_row(tokenizer, ROW, truth)
    assert row['prompt_count'] == 712 and row['target_count'] == 47
    assert len(row['input_ids']) == 759
    assert row['input_ids'][-1] == tokenizer.eos_token_id
    assert all(item == -100 for item in row['labels'][:712])
    assert row['labels'][712:] == row['input_ids'][712:]
    assert tokenizer.eos_token_id in row['input_ids'][:712]


def test_prompt_rejects_forward_information_by_construction(tokenizer):
    poisoned = {**ROW, 'expected': {'moving_piece': 'wrong'}, 'pv': 'answer', 'post_fen': 'future'}
    assert native_prompt(tokenizer, poisoned) == native_prompt(tokenizer, ROW)


def test_left_padding_retains_each_target_prediction(tokenizer):
    import torch
    first = native_training_row(tokenizer, ROW, core.expected_facts(FEN, 'e2e4'))
    second_row = {'case_id': 'ep', 'fen': '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1', 'selected_uci': 'e5d6'}
    second = native_training_row(tokenizer, second_row, core.expected_facts(second_row['fen'], 'e5d6'))
    batch, count = collate_training([first, second], tokenizer.pad_token_id, torch, 'cpu')
    assert batch['labels'].shape == (2, 128)
    assert count == first['target_count'] + second['target_count']
    assert int((batch['labels'][:, 1:] != -100).sum()) == count
    zeros = batch['attention_mask'][1] == 0
    assert zeros.any() and torch.all(batch['position_ids'][1][zeros] == 0)
    bad = dict(first, target_count=128, labels=[-100]*(len(first['input_ids'])-128)+first['input_ids'][-128:])
    with pytest.raises(ValueError, match='drop target'):
        collate_training([bad], tokenizer.pad_token_id, torch, 'cpu')


def test_eos_and_decode_never_repair(tokenizer):
    ids = tokenizer.encode('{"answer":true}', add_special_tokens=False)
    assert decode_generated(tokenizer, ids)['status'] == 'truncated'
    result = decode_generated(tokenizer, ids+[151645,151643])
    assert result['status'] == 'completed' and result['text'] == '{"answer":true}'
    with pytest.raises(ValueError, match='nonpadding'):
        decode_generated(tokenizer, ids+[151645,1])


@pytest.mark.parametrize('kind', ['fenced', 'extra', 'duplicate', 'truncated', 'error', 'not_run', 'unknown'])
def test_strict_score_uses_full_planned_denominator(tmp_path, kind):
    truth = core.expected_facts(FEN, 'e2e4')
    text = json.dumps(truth)
    if kind == 'fenced': text = '```json\n'+text+'\n```'
    if kind == 'extra': text = json.dumps({**truth, 'reason': 'x'})
    if kind == 'duplicate': text = text[:-1]+',"is_capture":false}'
    if kind == 'unknown': text = json.dumps({**truth, 'moving_piece': 'unknown'})
    status = kind if kind in ('truncated', 'error', 'not_run') else 'completed'
    raw = tmp_path/'raw'
    seal_raw(raw, [{'case_id':'fixture','status':status,'text':text}], ['fixture'], {})
    labels = tmp_path/'labels.json'
    save(labels, {'rows':[{'case_id':'fixture','expected':truth}]})
    score = score_sealed(raw, labels, sha(labels))
    assert score['counts']['planned'] == 1 and score['counts']['all_eight_correct'] == 0
    if kind != 'unknown':
        assert all(item['correct'] == 0 for item in score['fields'].values())
    else:
        assert score['fields']['moving_piece']['unknown'] == 1


def test_seal_is_verified_before_labels_are_opened(tmp_path):
    raw = tmp_path/'raw'
    seal_raw(raw, [{'case_id':'x','status':'not_run','text':''}], ['x'], {})
    (raw/'raw.json').write_text('{}')
    with pytest.raises(ValueError, match='seal mismatch'):
        score_sealed(raw, tmp_path/'DOES_NOT_EXIST', '0'*64)
    with pytest.raises(ValueError, match='overwritten'):
        seal_raw(raw, [], [], {})


def test_label_mutation_is_rejected_before_truth_join(tmp_path):
    raw = tmp_path/'raw'
    seal_raw(raw, [{'case_id':'fixture','status':'not_run','text':''}], ['fixture'], {})
    labels = tmp_path/'labels.json'
    save(labels, {'rows':[{'case_id':'fixture','expected':core.expected_facts(FEN,'e2e4')}]})
    expected_hash = sha(labels)
    labels.write_text('mutated invalid JSON')
    with pytest.raises(ValueError, match='label hash mismatch'):
        score_sealed(raw, labels, expected_hash)


def test_selection_ties_and_incomplete_checkpoints():
    scores = [{'step':step,'counts':{'planned':128,'all_eight_correct':10,
        'strict_parse_completed':120,'error':0,'not_run':0}} for step in [0,128,256,512,1024]]
    assert select_checkpoint(scores)['selected_step'] == 0
    scores[2]['counts']['strict_parse_completed'] = 121
    assert select_checkpoint(scores)['selected_step'] == 256
    scores[4]['counts']['all_eight_correct'] = 11
    assert select_checkpoint(scores)['selected_step'] == 1024
    scores[4]['counts']['not_run'] = 1
    with pytest.raises(ValueError, match='incomplete'):
        select_checkpoint(scores)
    with pytest.raises(ValueError, match='all predeclared'):
        select_checkpoint(scores[:-1])


@pytest.mark.parametrize('now,phase,expected', [
    (3599,{},False),(3600,{},True),
    (4000,{'phase':'holdout','started_monotonic':3500},False),
    (5300,{'phase':'holdout','started_monotonic':3500},True),
    (4000,{'phase':'holdout','started_monotonic':3601},True),
    (4000,{'phase':'holdout','started_monotonic':float('nan')},True)])
def test_owned_phase_deadlines(now, phase, expected):
    assert bool(phase_deadline(0, phase, now)) is expected


def test_only_exact_owned_handle_timeout_policy():
    assert not termination_due(None, 10000)
    assert not termination_due(10, 39.999)
    assert termination_due(10, 40)


def test_supervisor_cancels_and_terminates_only_its_own_child(tmp_path, monkeypatch):
    import io
    from types import SimpleNamespace
    import chess_fact_sft_supervise as supervisor
    from chess_native_resources import Sample, GIB
    repo = tmp_path/'repo'
    (repo/'scripts').mkdir(parents=True)
    for name in ['chess_native_resources.py', 'chess_board_fact_core.py']:
        (repo/'scripts'/name).write_text('# fake fixture only\n')
    private = repo/'data/private/chess-fact-sft-v1'
    cohort = private/'cohort'
    cohort.mkdir(parents=True)
    save(cohort/'frozen-data.json', {'files_sha256':{}})
    for name in ('dev-inputs.json','holdout-inputs.json'):
        save(cohort/name, {'rows':[]})
    protocol = repo/'protocol.json'
    save(protocol, {'status':'FROZEN_BEFORE_COHORT_SELECTION_IMPLEMENTATION_AND_PRETRAINED_FORWARD'})
    state = {'clock':0., 'samples':0}
    def sample():
        state['samples'] += 1
        return Sample(32*GIB, 12*GIB if state['samples']<=10 else 3*GIB,
            48*GIB, 24*GIB, 16*GIB, 14*GIB)
    class OwnedChild:
        pid = 123456
        returncode = None
        terminations = 0
        def poll(self): return self.returncode
        def terminate(self):
            self.terminations += 1
            self.returncode = 1
        def wait(self, timeout): return self.returncode
    owned = OwnedChild()
    monkeypatch.setattr(supervisor, 'windows_sample', sample)
    monkeypatch.setattr(supervisor, 'urlopen', lambda *a, **k: io.BytesIO(b'{"models":[]}'))
    monkeypatch.setattr(supervisor.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='0\n'))
    monkeypatch.setattr(supervisor.subprocess, 'Popen', lambda *a, **k: owned)
    monkeypatch.setattr(supervisor.time, 'monotonic', lambda: state['clock'])
    monkeypatch.setattr(supervisor.time, 'sleep', lambda amount: state.__setitem__('clock',state['clock']+amount))
    out = private/'run'
    with pytest.raises(RuntimeError, match='retain artifacts'):
        supervisor.run(repo, cohort, protocol, out)
    assert owned.terminations == 1
    assert read(out/'ownership.json')['pid'] == owned.pid
    result = read(out/'supervision.json')
    assert result['forced_owned_termination'] and result['exit_code'] == 1
    assert result['cancel_issues'] == ['physical_available_bytes_below_reserve']
    assert (out/'cancel.json').exists()


def test_full_denominator_recovery_keeps_partial_and_unstarted_cohorts(tmp_path):
    declare_run(tmp_path, ['d1','d2'], ['h1'])
    save(tmp_path/'progress.json', {'cohort':'dev-0','attempted_case':'d2'})
    journal = tmp_path/'dev-0.journal.jsonl'
    journal.write_text(json.dumps({'case_id':'d1','status':'truncated','text':'raw partial','new_ids':[3,4]})+'\n{broken')
    finalize_run_ledger(tmp_path)
    value = read(tmp_path/'outcome-ledger.json')
    assert value['planned'] == 12 and sum(map(len,value['cohorts'].values())) == 12
    assert value['cohorts']['dev-0'][0]['new_ids'] == [3,4]
    assert value['cohorts']['dev-0'][1]['actual_call_status'] == 'unknown_after_local_failure'
    assert all(row['status']=='not_run' for name,rows in value['cohorts'].items() if name!='dev-0' for row in rows)
    assert value['recovery_notes'][0]['journal_partial_or_invalid']
