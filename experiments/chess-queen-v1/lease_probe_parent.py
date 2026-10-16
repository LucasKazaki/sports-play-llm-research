"""CPU-only interrupted-parent regression fixture; never imports a model."""
import argparse
from pathlib import Path
import time

import gpu_worker


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--marker',type=Path,required=True)
    args=parser.parse_args()
    original=gpu_worker.OwnedWindowsJob
    def pause_before_assignment(child):
        time.sleep(10)
        return original(child)
    gpu_worker.OwnedWindowsJob=pause_before_assignment
    gpu_worker.run_worker(['experiments/chess-queen-v1/lease_probe_child.py',
        '--marker',str(args.marker)],args.receipt,maximum_seconds=20,lock_path=args.lock)


if __name__=='__main__':main()
