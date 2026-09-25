import json
from pathlib import Path

SCHEMA = Path(__file__).parents[1] / "prototype" / "chess_concept_explanation.schema.json"
CONCEPTS = {"king_safety", "material", "development", "center", "piece_activity", "pawn_structure", "space", "tactical_threat", "endgame_transition"}

def load_schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))

def test_explanation_schema_has_versioned_grounding_contract():
    schema = load_schema()
    assert schema["title"] == "ConceptExplanationV1"
    assert {"abstain", "verdict", "confidence", "concepts", "engine_evidence_refs", "commentary_evidence_refs"} <= set(schema["required"])
    assert set(schema["properties"]["concepts"]["items"]["enum"]) == CONCEPTS
    assert schema["properties"]["engine_evidence_refs"]["items"]["type"] == "string"
    assert schema["properties"]["commentary_evidence_refs"]["items"]["type"] == "string"

def test_explanation_schema_requires_nonabstaining_claim_structure():
    schema = load_schema()
    non_abstaining = schema["allOf"][0]["then"]
    assert non_abstaining["properties"]["verdict"]["const"] == "concept_explanation"
    assert {"move_summary", "primary_concepts", "limitations"} <= set(non_abstaining["required"])
    primary = schema["properties"]["primary_concepts"]["items"]
    assert primary["additionalProperties"] is False
    assert {"concept", "claim", "evidence_refs"} <= set(primary["required"])
    assert primary["properties"]["evidence_refs"]["minItems"] == 1

def test_explanation_schema_requires_matching_abstention_verdict():
    schema = load_schema()
    abstaining = schema["allOf"][1]["then"]
    assert abstaining["properties"]["verdict"]["const"] == "abstain"
