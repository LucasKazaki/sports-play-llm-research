"""Attach audited native metadata to a local checkpoint without changing weights."""
import argparse
import json
import shutil
from pathlib import Path

from chess_classifier_adapter import load_native_contract
from chess_stockfish_distill import digest, save

METADATA = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "tokenizer.py", "README.md")


def package_checkpoint(base_dir, checkpoint_dir):
    base_dir, checkpoint_dir = Path(base_dir), Path(checkpoint_dir)
    original_contract = load_native_contract(base_dir)
    weight = checkpoint_dir / "model.safetensors"
    before = digest(weight)
    base_config = json.loads((base_dir / "config.json").read_text())
    checkpoint_config = json.loads((checkpoint_dir / "config.json").read_text())
    for key in ("id2label", "label2id", "vocab_size", "pad_token_id", "model_type", "hidden_size", "num_hidden_layers"):
        if checkpoint_config.get(key) != base_config.get(key):
            raise ValueError(f"checkpoint native contract differs: {key}")
    copied = {}
    for name in METADATA:
        source, target = base_dir / name, checkpoint_dir / name
        if not source.exists():
            raise ValueError(f"required pinned metadata absent: {name}")
        if target.exists() and digest(target) != digest(source):
            raise ValueError(f"refusing to replace different checkpoint metadata: {name}")
        if not target.exists():
            shutil.copyfile(source, target)
        copied[name] = digest(target)
    contract = load_native_contract(checkpoint_dir)
    if contract["id2label"] != original_contract["id2label"] or contract["vocab"] != original_contract["vocab"]:
        raise ValueError("packaged native mapping changed")
    if digest(weight) != before:
        raise ValueError("checkpoint weights changed during metadata packaging")
    receipt = {"schema": "chess.classifier-checkpoint-package.v1", "weight_sha256_before": before,
               "weight_sha256_after": digest(weight), "metadata_sha256": copied,
               "implementation_sha256": digest(Path(__file__)), "remote_python_executed": False}
    save(checkpoint_dir / "metadata-package.json", receipt)
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-dir", type=Path, required=True)
    p.add_argument("--checkpoint-dir", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(package_checkpoint(args.base_dir, args.checkpoint_dir)))
