"""CPU-only lifecycle fixture for GPU lease software checks."""
import argparse
from pathlib import Path
import time
parser=argparse.ArgumentParser();parser.add_argument('--sleep',type=float,default=0);parser.add_argument('--marker',type=Path)
args=parser.parse_args()
if args.marker:args.marker.write_text('started',encoding='utf-8')
time.sleep(min(args.sleep,5))
print('CPU lease fixture finished')
