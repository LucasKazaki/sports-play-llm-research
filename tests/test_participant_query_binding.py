"""Bounded planner-attribute regressions: saved/stub responses, zero inference."""
import copy
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'prototype'))
import search_demo_server as module

SAVED = ROOT / 'artifacts/project-capability-20260908/local-model-experiment-v1'


def plan(*, participants=(), search_terms=('shot',)):
    return {'intent_summary': 'Synthetic attribute-binding check', 'event_types': ['shot_on_target'],
            'search_terms': list(search_terms), 'participant_terms': list(participants),
            'phases': [], 'field_areas': [], 'explanation': 'Synthetic software fixture; no visual evidence.'}


def wire(monkeypatch, raw):
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self):
            return json.dumps({'model': 'synthetic-saved-transport', 'choices': [
                {'message': {'content': json.dumps(raw)}}]}).encode()
    def response(*_args, **_kwargs):
        calls.append('saved_or_synthetic_only')
        return Response()
    monkeypatch.setattr(module, '_loopback_urlopen', response)
    return calls


@pytest.mark.parametrize('query,raw', [
    ('Find shots', plan(participants=['player with jersey number 10'])),
    ('Find shots by jersey 8', plan(participants=['jersey 10'])),
    ('Find shots at 10 minutes', plan(participants=['jersey 10'])),
    ('Find 10 shots', plan(participants=['number 10'])),
    ('Find shots by #100', plan(participants=['#10'])),
    ('Find shots by jersey 10.5', plan(participants=['jersey 10'])),
    ('Find shots', plan(participants=['wearing red kit'])),
    ('Find shots and red cards', plan(participants=['wearing red kit'])),
    ('Find shots by a player wearing blue', plan(participants=['wearing red'])),
    ('Find shots by the blue shirt', plan(participants=['red shirt'])),
    ('Find shots', plan(search_terms=['shot', 'jersey 10'])),
    ('Find shots', plan(search_terms=['shot', 'blue kit'])),
])
def test_unsupported_explicit_attribute_uses_disclosed_fallback(monkeypatch, query, raw):
    calls = wire(monkeypatch, raw)
    result = module.interpret_coach_query(query)
    assert len(calls) == 1
    assert result['source'] == 'deterministic_literal_fallback'
    assert result['plan']['participant_terms'] == []
    assert 'unsupported participant attributes' in result['error']


@pytest.mark.parametrize('query,participants', [
    ('Show shot number 10', ['jersey 10']),
    ('Show shots from clip no. 10', ['jersey 10']),
    ('Show shots by player 10 wearing red kit against player 7 wearing blue kit', ['player 10 wearing blue kit']),
    ('Show shots by player 10 wearing red kit against player 7 wearing blue kit', ['player 7 wearing red kit']),
    ('Show shots; ignore the player wearing red kit', ['wearing red kit']),
    ('Find shots not by jersey 10', ['jersey 10']),
    ('Find shots excluding players wearing red kit', ['wearing red kit']),
    ('Find shots by jersey 10 after the player wearing red kit passed', ['jersey 10', 'red kit']),
])
def test_ambiguous_participant_scope_uses_disclosed_fallback(monkeypatch, query, participants):
    # These are constructed adversarial requests, not empirical soccer labels.
    calls = wire(monkeypatch, plan(participants=participants, search_terms=['shot', 'pass']))
    result = module.interpret_coach_query(query)
    assert len(calls) == 1
    assert result['source'] == 'deterministic_literal_fallback'
    assert result['plan']['participant_terms'] == []
    assert 'bounded positive single-participant binding' in result['error']


@pytest.mark.parametrize('raw', [
    plan(participants=['not jersey 10']),
    plan(search_terms=['shot', 'ignore the player wearing red kit']),
])
def test_nonpositive_attribute_terms_cannot_rebind_clear_request(monkeypatch, raw):
    wire(monkeypatch, raw)
    result = module.interpret_coach_query('Find shots by jersey 10 wearing red kit')
    assert result['source'] == 'deterministic_literal_fallback'
    assert result['plan']['participant_terms'] == []
    assert 'bounded positive single-participant binding' in result['error']


def saved_distractor():
    response = json.loads((SAVED / 'response-03-distractor.json').read_text(encoding='utf-8'))
    return json.loads(response['choices'][0]['message']['content'])


def test_exact_saved_kit_response_uses_disclosed_fallback(monkeypatch):
    # Exact previously generated output and query. No response regeneration.
    query = 'Show the through pass, excluding the nearby unrelated pass.'
    raw = saved_distractor()
    assert 'wearing red kit' in raw['participant_terms'] and 'wearing blue kit' in raw['participant_terms']
    wire(monkeypatch, raw)
    result = module.interpret_coach_query(query)
    assert result['source'] == 'deterministic_literal_fallback'
    assert 'kit:blue' in result['error'] and 'kit:red' in result['error']
    assert result['raw_interpretation'] is not None


def test_invented_kit_cannot_boost_synthetic_saved_report(monkeypatch, tmp_path):
    # Synthetic ranking counterexample using the unchanged saved planner output.
    # This does not assess the truth of any actual soccer report or image.
    raw = saved_distractor()
    wire(monkeypatch, raw)
    result = module.interpret_coach_query('Show the through pass, excluding the nearby unrelated pass.')
    database = tmp_path / 'synthetic.sqlite3'
    report = {'event_types': raw['event_types'], 'primary_action': 'through pass',
              'phase_of_play': 'unknown', 'field_areas': [], 'participants': []}
    with sqlite3.connect(database) as db:
        db.executescript('CREATE TABLE windows(window_id TEXT,match_id TEXT,status TEXT);'
                        'CREATE TABLE events(event_id TEXT,window_id TEXT,start_s REAL,end_s REAL,confidence REAL,report_json TEXT);')
        db.execute("INSERT INTO windows VALUES('synthetic-window','synthetic-match','complete')")
        for event_id, start, participant in [('SYNTHETIC-neutral', 1, 'player'), ('SYNTHETIC-red', 2, 'wearing red kit')]:
            row = copy.deepcopy(report)
            row['participants'] = [{'player_reference': participant}]
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',
                       (event_id, 'synthetic-window', start, start + 1, 0.5, json.dumps(row)))
    ranked = module.rank_saved_events(database, result['plan'])
    assert [row['event_id'] for row in ranked] == ['SYNTHETIC-neutral', 'SYNTHETIC-red']
    assert all(match['kind'] != 'participant' for row in ranked for match in row['matched_on'])


@pytest.mark.parametrize('query,raw', [
    ('Find shots by jersey 10.', plan(participants=['player with jersey number 10'])),
    ('Find shots by shirt no. 8', plan(participants=['number 8'])),
    ('Find shots by #10', plan(participants=['jersey 10'])),
    ('Find shots by player 7', plan(participants=['shirt 7'])),
    ('Find shots by number 8', plan(participants=['player #8'])),
    ('Find shots by jersey 010', plan(participants=['jersey 10'])),
    ('Find shots by players wearing red', plan(participants=['red kit'])),
    ('Find shots by the blue shirt', plan(participants=['wearing blue kit'])),
    ('Find shots by the grey kit', plan(participants=['wearing gray'])),
    ('Find shots by jersey 10 in the red kit', plan(participants=['red shirt', '#10'])),
    ('Show me shots by player 10 wearing red kit.', plan(participants=['player 10 wearing red kit'])),
    ('Find shots on goal by #8 wearing blue uniform', plan(participants=['#8', 'wearing blue'], search_terms=['shot', 'goal'])),
    ('Show pass by jersey 8', plan(participants=['jersey 8'], search_terms=['pass'])),
    ('Find shots', plan(participants=['goalkeeper'])),
    ('Find shots', plan()),
])
def test_supported_or_out_of_scope_attributes_keep_existing_path(monkeypatch, query, raw):
    wire(monkeypatch, raw)
    result = module.interpret_coach_query(query)
    assert result['source'] == 'local_query_llm'
    assert result['plan']['participant_terms'] == [v.casefold() for v in raw['participant_terms']]


def test_saved_negation_still_stops_before_transport(monkeypatch):
    def prohibited(*_args, **_kwargs):
        raise AssertionError('Negation must stop before any provider call')
    monkeypatch.setattr(module, '_loopback_urlopen', prohibited)
    with pytest.raises(module.UnsupportedNegationConstraint):
        module.interpret_coach_query('Find cutbacks without a shot')


def test_queryless_validation_retains_schema_only_scope():
    assert module.validate_query_plan(plan(participants=['jersey 10']))['participant_terms'] == ['jersey 10']
