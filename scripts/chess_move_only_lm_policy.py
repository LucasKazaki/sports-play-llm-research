"""Explicit local use of the frozen first-M move-only language-policy task."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import chess_move_only_lm_v4 as experiment
import chess_stockfish_distill as core


def policy_result(fen, raw_output, token_ids):
    move = experiment.parse_action(raw_output)
    legal = core.legal_action(fen, move)
    return {"schema": "chess.move-only-lm.policy.v4", "fen": fen, "accepted": legal,
            "move_uci": move if legal else None, "raw_move_uci": move,
            "raw_output": raw_output, "generated_token_ids": token_ids,
            "reason": "legal_first_token_candidate" if legal else "raw_parse_or_legality_failure",
            "selection_mode": "raw_first_M_no_mask_or_late_rescue",
            "limitations": ["Experimental move-only language policy; no commentary or rating claim.",
                            "Explicit model directory required; no automatic checkpoint promotion."]}


def predict(fen, model_dir, device="auto"):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    prompt = experiment.prompt_for({"fen": fen})
    torch.set_num_threads(4)
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True,
                                                attn_implementation="sdpa").float().to(device).eval()
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(device)
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=16, do_sample=False,
                                   pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
    ids = generated[0, inputs["input_ids"].shape[1]:].cpu().tolist()
    result = policy_result(fen, tokenizer.decode(ids, skip_special_tokens=True), ids)
    result.update(model_weight_sha256=core.digest(Path(model_dir) / "model.safetensors"), device=device,
                  policy_source_sha256=core.digest(Path(__file__)),
                  experiment_source_sha256=core.digest(Path(experiment.__file__)))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fen", required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = predict(args.fen, args.model_dir, args.device)
    if args.out:
        core.save(args.out, result)
    print(json.dumps(result))
    raise SystemExit(0 if result["accepted"] else 2)
