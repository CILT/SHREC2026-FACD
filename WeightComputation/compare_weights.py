"""Compare the weights computed by compute_weights.py with the ones used in the
paper (gt_curvature_paper.json, distributed with the evaluation data)."""
import argparse
import json
import os

import numpy as np


def load(path):
    with open(path) as f:
        data = json.load(f)
    return np.array([data[str(i)] for i in range(len(data))])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare recomputed FACD weights with the paper's weights.")
    parser.add_argument("--root_dir", type=str, required=True, help="Root directory containing experiment folders.")
    parser.add_argument("--computed", type=str, default="gt_curvature.json")
    parser.add_argument("--reference", type=str, default="gt_curvature_paper.json")
    args = parser.parse_args()

    for exp_name in sorted(os.listdir(args.root_dir)):
        computed = os.path.join(args.root_dir, exp_name, args.computed)
        reference = os.path.join(args.root_dir, exp_name, args.reference)
        if not (os.path.exists(computed) and os.path.exists(reference)):
            continue
        a, b = load(computed), load(reference)
        if a.shape != b.shape:
            print(f"{exp_name}: different number of vertices ({len(a)} vs {len(b)})")
            continue
        diff = np.abs(a - b)
        n = int((diff > 0).sum())
        if n == 0:
            print(f"{exp_name}: identical to the paper's weights ({len(a)} vertices)")
        else:
            print(f"{exp_name}: {n} of {len(a)} vertices differ from the paper's weights "
                  f"(max |diff| = {diff.max():.4f}, mean weight {a.mean():.4f} vs {b.mean():.4f})")
