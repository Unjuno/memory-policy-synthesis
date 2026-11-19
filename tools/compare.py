#!/usr/bin/env python3
"""Exploratory, NON-STATISTICAL comparison of stage-0 runs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('baseline')
ap.add_argument('candidate')
args = ap.parse_args()
base = json.loads(Path(args.baseline).read_text())
new = json.loads(Path(args.candidate).read_text())
if (base['config'] != new['config'] or base['kernel'] != new['kernel']
        or base.get('machine') != new.get('machine')):
    raise SystemExit('INVALID COMPARISON: kernel, machine or benchmark configuration differs')
if base['p95_ns'] <= 0:
    raise SystemExit('INVALID COMPARISON: baseline p95 must be positive')
percent = (1-new['p95_ns']/base['p95_ns'])*100
print(f'Baseline p95: {base["p95_ns"]/1e6:.3f} ms')
print(f'Candidate p95: {new["p95_ns"]/1e6:.3f} ms')
print(f'Exploratory p95 improvement: {percent:.2f}%')
print('NOT a statistically validated claim; collect paired randomized replicates.')
