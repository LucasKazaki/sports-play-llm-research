"""Separate file-only process: seal verification precedes evaluator label reads."""
import argparse
from pathlib import Path
from chess_fact_sft_common import save, score_sealed

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--expected-label-sha256', required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('score cannot be overwritten')
    save(args.out, score_sealed(args.raw, args.labels, args.expected_label_sha256))
