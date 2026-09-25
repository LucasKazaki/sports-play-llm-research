"""Build a synthetic-input fixture whose candidate IDs are Stockfish receipts."""
import argparse, json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    comparison = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    evidence = [{"id":item["id"], "move_uci":item["move_uci"], "score_cp":item["score_cp"]} for item in comparison["engine_evidence"]]
    if len(evidence) < 2: raise SystemExit("two_engine_candidates_required")
    fixture = dict(template)
    fixture["position_id"] = template["position_id"] + "-stockfish-19"
    fixture["move_uci"] = evidence[0]["move_uci"]
    fixture["engine_evidence"] = evidence
    fixture["commentary_evidence"] = []
    source_kind = "synthetic" if template["source"]["source_id"] == "synthetic-contract-fixture" else "real-source"
    fixture["limitations"] = list(template.get("limitations", [])) + ["Engine candidates are from Stockfish 19 receipt: " + args.comparison.replace("\\","/"), "This is one %s position; it is not calibration or training." % source_kind]
    Path(args.output).write_text(json.dumps(fixture, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"engine_fixture_ok":True, "move_uci":fixture["move_uci"], "candidate_ids":[item["id"] for item in evidence]}, sort_keys=True))

if __name__ == "__main__": main()
