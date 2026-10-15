"""Explicit local classifier inference; raw legality stays visible."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from chess_classifier_adapter import encode_fen, load_native_contract, rank_logits
from chess_stockfish_distill import digest, save


def policy_result(fen, logits, contract, use_legal_mask=False):
    ranked = rank_logits(fen, logits, contract["id2label"], top_k=5)
    selected = ranked["legal_choice_uci"] if use_legal_mask else ranked["raw_choice_uci"]
    accepted = selected is not None and (use_legal_mask or ranked["raw_choice_is_legal"])
    return {"schema": "chess.local-classifier-policy.v1", "fen": fen,
            "selection_mode": "legal_mask" if use_legal_mask else "raw",
            "accepted": accepted, "move_uci": selected if accepted else None,
            "reason": "legal_policy_candidate" if accepted else "raw_illegal_or_no_legal_action",
            **ranked,
            "limitations": ["Move-only classifier; no natural-language understanding or commentary is measured.",
                            "Legal masking uses deterministic board rules and is separate from raw model legality.",
                            "Logits are model rankings, not Stockfish scores, probabilities or guaranteed best play."]}


def predict(fen, model_dir, device="auto", use_legal_mask=False):
    import torch
    from transformers import LlamaForSequenceClassification
    contract = load_native_contract(model_dir)
    encoded = encode_fen(fen, contract)
    torch.set_num_threads(4)
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LlamaForSequenceClassification.from_pretrained(model_dir, local_files_only=True,
                                                           attn_implementation="sdpa").float().to(device).eval()
    inputs = {k: torch.tensor([v], dtype=torch.long, device=device) for k, v in encoded.items()}
    with torch.inference_mode():
        logits = model(**inputs).logits[0].float().cpu().tolist()
    result = policy_result(fen, logits, contract, use_legal_mask)
    result.update(device=device, model_sha256=digest(Path(model_dir)/"model.safetensors"),
                  adapter_source_sha256=contract["source_sha256"])
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fen", required=True)
    p.add_argument("--model-dir", type=Path, required=True, help="Explicit local model directory; no automatic checkpoint promotion")
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    p.add_argument("--legal-mask", action="store_true", help="Opt in to rule-assisted selection; raw result remains visible")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    result = predict(args.fen, args.model_dir, args.device, args.legal_mask)
    if args.out:
        save(args.out, result)
    print(json.dumps(result))
    raise SystemExit(0 if result["accepted"] else 2)
