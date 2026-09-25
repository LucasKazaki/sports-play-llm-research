"""Command-line interface for the standalone SoccerMaster scale experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manifest import build_manifest, verify_manifest
from .model import extract_features, fetch_backbone, train_and_evaluate, verify_package
from .vlm_eval import freeze_subset, run_inference, score, verify_evaluation


ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "data/private/soccermaster-scale-v1/raw"
PRIVATE_DIR = ROOT / "data/private/soccermaster-scale-v1/experiment"
ACQUISITION_DIR = ROOT / "artifacts/soccermaster-scale-v1/acquisition"
ARTIFACT_DIR = ROOT / "artifacts/soccermaster-scale-v1"
BACKBONE = ARTIFACT_DIR / "backbone/mobilenetv2-12.onnx"
BACKBONE_RECEIPT = ARTIFACT_DIR / "backbone/mobilenetv2-12.receipt.json"
CORPUS_RECEIPT = ARTIFACT_DIR / "corpus-receipt.json"
MODEL_DIR = ARTIFACT_DIR / "pilot-v1"
VLM_PRIVATE_DIR = ROOT / "data/private/soccermaster-scale-v1/vlm-eval"
VLM_ARTIFACT_DIR = ARTIFACT_DIR / "vlm-eval-v1"
VLM_SUBSET_RECEIPT = ARTIFACT_DIR / "vlm-subset-receipt.json"
VLM_RUN_RECEIPT = VLM_ARTIFACT_DIR / "run-receipt.json"
RUNTIME_RECEIPT = ROOT / "artifacts/soccernet-pilot-v1/isolated-vlm-runtime-receipt-v1.json"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    sub = value.add_subparsers(dest="command", required=True)
    sub.add_parser("build-manifest")
    sub.add_parser("verify-manifest")
    sub.add_parser("fetch-backbone")
    sub.add_parser("extract-features")
    train = sub.add_parser("train")
    train.add_argument("--epochs", type=int, default=350)
    sub.add_parser("verify-package")
    sub.add_parser("freeze-vlm-subset")
    sub.add_parser("run-vlm")
    sub.add_parser("score-vlm")
    sub.add_parser("verify-vlm")
    sub.add_parser("run-all")
    return value


def main() -> int:
    args = parser().parse_args()
    manifest_path = PRIVATE_DIR / "manifest.json"
    examples_path = PRIVATE_DIR / "examples.jsonl"
    feature_dir = PRIVATE_DIR / "features"
    feature_index = PRIVATE_DIR / "feature-index.json"
    outputs: list[dict[str, object]] = []
    if args.command in {"build-manifest", "run-all"}:
        manifest, receipt = build_manifest(
            raw_root=RAW_ROOT, acquisition_dir=ACQUISITION_DIR,
            private_output_dir=PRIVATE_DIR, public_receipt_path=CORPUS_RECEIPT,
        )
        outputs.append({"stage": "manifest", "games": manifest["corpus"]["game_count"], "hours": manifest["corpus"]["total_duration_hours"], "examples": manifest["corpus"]["example_count"], "status": receipt["status"]})
    if args.command in {"verify-manifest", "run-all"}:
        outputs.append({"stage": "verify_manifest", **verify_manifest(manifest_path=manifest_path, examples_path=examples_path, public_receipt_path=CORPUS_RECEIPT, raw_root=RAW_ROOT)})
    if args.command in {"fetch-backbone", "run-all"}:
        receipt = fetch_backbone(output_path=BACKBONE, receipt_path=BACKBONE_RECEIPT)
        outputs.append({"stage": "backbone", "status": "verified", "sha256": receipt["sha256"]})
    if args.command in {"extract-features", "run-all"}:
        index = extract_features(examples_path=examples_path, raw_root=RAW_ROOT, backbone_path=BACKBONE, feature_dir=feature_dir, feature_index_path=feature_index)
        outputs.append({"stage": "features", "status": "verified", "example_count": index["example_count"], "elapsed_seconds": index["elapsed_seconds"]})
    if args.command in {"train", "run-all"}:
        result = train_and_evaluate(
            examples_path=examples_path, feature_dir=feature_dir, feature_index_path=feature_index,
            backbone_receipt_path=BACKBONE_RECEIPT, corpus_receipt_path=CORPUS_RECEIPT,
            output_dir=MODEL_DIR, epochs=args.epochs if args.command == "train" else 350,
        )
        outputs.append({"stage": "train", "status": result["status"], "generation": result["model_generation"], "test": result["metrics"]["test"]})
    if args.command in {"verify-package", "run-all"}:
        outputs.append({"stage": "verify_package", **verify_package(
            output_dir=MODEL_DIR, examples_path=examples_path, feature_dir=feature_dir,
            feature_index_path=feature_index, backbone_receipt_path=BACKBONE_RECEIPT,
            corpus_receipt_path=CORPUS_RECEIPT,
        )})
    if args.command == "freeze-vlm-subset":
        outputs.append({"stage": "freeze_vlm_subset", **freeze_subset(
            examples_path=examples_path, private_dir=VLM_PRIVATE_DIR,
            public_receipt_path=VLM_SUBSET_RECEIPT,
        )})
    if args.command == "run-vlm":
        outputs.append({"stage": "run_vlm", **run_inference(
            frozen_inputs_path=VLM_PRIVATE_DIR / "frozen-inputs.json",
            subset_receipt_path=VLM_SUBSET_RECEIPT, raw_root=RAW_ROOT,
            private_run_dir=VLM_PRIVATE_DIR / "run-v1", public_run_receipt_path=VLM_RUN_RECEIPT,
            runtime_receipt_path=RUNTIME_RECEIPT,
        )})
    if args.command == "score-vlm":
        outputs.append({"stage": "score_vlm", **score(
            frozen_inputs_path=VLM_PRIVATE_DIR / "frozen-inputs.json",
            sealed_labels_path=VLM_PRIVATE_DIR / "sealed-labels.json",
            subset_receipt_path=VLM_SUBSET_RECEIPT, private_run_dir=VLM_PRIVATE_DIR / "run-v1",
            public_run_receipt_path=VLM_RUN_RECEIPT, output_dir=VLM_ARTIFACT_DIR,
        )})
    if args.command == "verify-vlm":
        outputs.append({"stage": "verify_vlm", **verify_evaluation(
            frozen_inputs_path=VLM_PRIVATE_DIR / "frozen-inputs.json",
            sealed_labels_path=VLM_PRIVATE_DIR / "sealed-labels.json",
            subset_receipt_path=VLM_SUBSET_RECEIPT, private_run_dir=VLM_PRIVATE_DIR / "run-v1",
            public_run_receipt_path=VLM_RUN_RECEIPT, output_dir=VLM_ARTIFACT_DIR,
        )})
    print(json.dumps(outputs[0] if len(outputs) == 1 else outputs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
