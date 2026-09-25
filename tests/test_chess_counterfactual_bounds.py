"""Synthetic protocol controls on real development inputs; not engine quality evidence."""
import copy
import importlib.util
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('bound_counterfactual', ROOT / 'scripts/chess_counterfactual_evidence.py')
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)
from test_chess_counterfactual_streaming import ParserEngine
DATA = ROOT / 'data/open/chess/lichess-real-seed-v1'


@pytest.mark.parametrize('bound', ['lowerbound', 'upperbound'])
def test_latest_qualified_observations_remain_explicit_and_distinct(bound):
    value = cf.collect_receipt(DATA, ParserEngine(early_bound='', final_bound=bound), cf.ENGINE_SHA256, allow_bounds=True)
    result = cf.verify_receipt(DATA, value)
    assert value['schema'] == 'chess-counterfactual-evidence/v3'
    assert result['complete'] is True and result['requested_positions'] == 8
    assert result['exact_candidates'] == result['qualified_candidates'] == 8
    assert result['engine_scores_independently_reproduced'] is False
    for row in value['results']:
        assert row['candidates'][0]['score']['bound'] == bound[:-5]
        assert row['candidates'][1]['score']['bound'] == 'exact'
        assert row['candidates'][0]['score']['order'] == 'engine_score'
    assert 'chess_score_bounds.py' in value['implementation_sha256']


@pytest.mark.parametrize('field,value', [('bound', 'confidence'), ('bound', None),
    ('order', 'centipawn_interval'), ('side_to_move', 'invented')])
def test_invalid_qualification_cannot_verify_even_with_recomputed_candidate_hash(field, value):
    receipt = cf.collect_receipt(DATA, ParserEngine(early_bound='', final_bound='lowerbound'), cf.ENGINE_SHA256, allow_bounds=True)
    candidate = receipt['results'][0]['candidates'][0]
    candidate['score'][field] = value
    source, _ = cf.load_development(DATA)
    candidate['evidence_id'] = cf.candidate_id(source['items'][0], candidate, receipt['source_manifest_sha256'], cf.ENGINE_SHA256)
    with pytest.raises(ValueError):
        cf.verify_receipt(DATA, receipt)


def test_v3_cannot_be_relabelled_as_v2_and_original_strict_mode_remains():
    strict = cf.collect_receipt(DATA, ParserEngine(early_bound='', final_bound='upperbound'), cf.ENGINE_SHA256)
    assert cf.verify_receipt(DATA, strict)['failed_positions'] == 8
    value = cf.collect_receipt(DATA, ParserEngine(early_bound='', final_bound='upperbound'), cf.ENGINE_SHA256, allow_bounds=True)
    value['schema'] = 'chess-counterfactual-evidence/v2'
    with pytest.raises(ValueError):
        cf.verify_receipt(DATA, value)
