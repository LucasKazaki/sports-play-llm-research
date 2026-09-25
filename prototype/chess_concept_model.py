"""Fail-closed loopback client for Chess Concept Model explanations."""
import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
try:
    from chess_concept_schema_validator import validate_explanation, validate_position
except ModuleNotFoundError:
    from .chess_concept_schema_validator import validate_explanation, validate_position
from scripts.chess_explanation_factuality import check_moving_piece

DEFAULT_ENDPOINT = "http://127.0.0.1:1234/v1/chat/completions"
DEFAULT_MODEL = "loops-gtx1080-qwen3-4b"
_ALLOWED = {"abstain", "verdict", "confidence", "concepts", "engine_evidence_refs", "commentary_evidence_refs", "move_summary", "primary_concepts", "limitations"}

def _abstain(reason, errors=(), rejected_model_shape=None):
    result = {"abstain": True, "verdict": "abstain", "confidence": 0.0, "concepts": [], "engine_evidence_refs": [], "commentary_evidence_refs": [], "reason": reason, "validation_errors": list(errors), "limitations": ["No chess explanation was accepted from the local model."]}
    if rejected_model_shape is not None: result["rejected_model_shape"] = rejected_model_shape
    return result

def _prompt(packet):
    evidence = {key: packet[key] for key in ("fen", "move_uci", "engine_evidence", "commentary_evidence")}
    contract = {"abstain": False, "verdict": "concept_explanation", "confidence": 0.5, "concepts": ["center"], "engine_evidence_refs": ["candidate-id"], "commentary_evidence_refs": [], "move_summary": "short evidence-bound summary", "primary_concepts": [{"concept": "center", "claim": "short evidence-bound claim", "evidence_refs": ["candidate-id"]}], "limitations": ["one bounded limitation"]}
    return "Return one JSON object only; no markdown. Allowed concepts only: king_safety, material, development, center, piece_activity, pawn_structure, space, tactical_threat, endgame_transition. verdict is abstain or concept_explanation. primary_concepts is a list of objects, and limitations is a list of strings. Reuse only supplied evidence IDs. If unable, return an abstention object. Shape example: " + json.dumps(contract, separators=(",", ":")) + "\nEvidence:\n" + json.dumps(evidence, sort_keys=True, separators=(",", ":"))

def generate(packet, endpoint=DEFAULT_ENDPOINT, model=DEFAULT_MODEL, request_opener=urlopen):
    gate = validate_position(packet)
    if not gate["valid"]:
        return _abstain("invalid_position_evidence", gate["errors"])
    payload = {"model": model, "messages": [{"role": "system", "content": "Answer only with valid JSON; do not reveal reasoning."}, {"role": "user", "content": _prompt(packet)}], "temperature": 0, "max_tokens": 384}
    try:
        request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        response = json.load(request_opener(request, timeout=180))
        result = json.loads(response["choices"][0]["message"]["content"])
    except (KeyError, TypeError, ValueError, OSError) as error:
        return _abstain("local_model_response_unusable", [type(error).__name__])
    if not isinstance(result, dict) or set(result) - _ALLOWED:
        return _abstain("local_model_response_unusable", ["unexpected_output_shape"])
    verdict = validate_explanation(packet, result)
    if not verdict["valid"]:
        shape = {"type": type(result).__name__}
        if isinstance(result, dict):
            shape["keys"] = sorted(result)
            primary = result.get("primary_concepts")
            shape["primary_concepts_type"] = type(primary).__name__
            if isinstance(primary, list): shape["primary_concept_item_keys"] = [sorted(item) if isinstance(item, dict) else type(item).__name__ for item in primary]
        return _abstain("local_model_response_unusable", verdict["errors"], shape)
    factuality = check_moving_piece(packet, result)
    if not factuality["passed"]:
        return _abstain("model_claim_conflicts_with_board", [finding["kind"] for finding in factuality["findings"]])
    if packet["source"]["source_id"] == "synthetic-contract-fixture":
        result["limitations"] = list(result.get("limitations", [])) + ["Synthetic contract fixture: candidate references are not engine receipts."]
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a guarded local chess concept explanation.")
    parser.add_argument("--packet", required=True); parser.add_argument("--model", default=DEFAULT_MODEL); parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = parser.parse_args(argv)
    try: packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(json.dumps(_abstain("packet_read_error", [type(error).__name__]))); return 2
    result = generate(packet, args.endpoint, args.model)
    print(json.dumps(result, sort_keys=True))
    return 0 if not result["abstain"] else 2

if __name__ == "__main__":
    raise SystemExit(main())