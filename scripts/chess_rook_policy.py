"""Run the pinned local ROOK policy with native input and fail-closed legality.

The base specialist is the default. Fine-tuned experiment checkpoints have not
earned promotion. This command does not generate commentary or claim Elo.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import chess
from chess_stockfish_distill import ROOT, digest, legal_action, save
from chess_stockfish_distill_v2 import prompt_for, parse_action


def checked_result(fen, raw):
    move, fallback = parse_action(raw)
    legal = legal_action(fen, move)
    return {"raw_output": raw, "raw_move_uci": move, "used_candidate_fallback": fallback,
            "accepted": legal, "move_uci": move if legal else None,
            "reason": "legal_policy_candidate" if legal else "unparseable_or_illegal_model_action"}


def predict(fen, model_path, device="auto"):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    board = chess.Board(fen)
    if not board.is_valid() or board.is_game_over():
        raise ValueError("valid nonterminal board required")
    torch.set_num_threads(8)
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, attn_implementation="sdpa").to(device).eval()
    prompt = prompt_for({"fen": board.fen()})
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=128, do_sample=False,
                                pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
    raw = tokenizer.decode(output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return {"schema": "chess.local-rook-policy.v1", "fen": board.fen(), "device": device,
            "model_sha256": digest(Path(model_path)/"model.safetensors"),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            **checked_result(board.fen(), raw),
            "limitations": ["Legal candidate, not guaranteed best play.", "Generated scores are unverified predictions, not engine evidence.",
                            "No Elo or commentary-quality claim."]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fen", required=True)
    p.add_argument("--model", type=Path, default=ROOT / "data/private/chess-distill-v1/base-model")
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    result = predict(args.fen, args.model, args.device)
    if args.out:
        save(args.out, result)
    print(json.dumps(result))
    raise SystemExit(0 if result["accepted"] else 2)
