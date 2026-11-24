#!/usr/bin/env python3
"""Evaluate a single reconstruction against a ground-truth mesh with CD and FACD.

This is a single-pair wrapper around the same code used to reproduce Table 4:
FACD_Evaluation/compute_facd.py (distances) and
WeightComputation/compute_weights.py (curvature-based weights). Reconstructions
must already be registered to the ground-truth frame (paper Sec. 3.3).

Examples:
    # Weights are taken from gt_curvature.json next to gt.obj, or computed.
    .env/bin/python scripts/evaluate_reconstruction.py \
        --ground_truth   data/SHREC2026_FACD_Table4/<object>/gt.obj \
        --reconstruction data/SHREC2026_FACD_Table4/<object>/SAMplify_SuGaR.obj \
        --output_csv     results/sample_evaluation.csv

    # Use a specific weights file (e.g. the ones distributed with the paper).
    .env/bin/python scripts/evaluate_reconstruction.py \
        --ground_truth   gt.obj \
        --reconstruction my_reconstruction.ply \
        --weights        gt_curvature_paper.json
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "FACD_Evaluation"))
sys.path.insert(0, str(ROOT / "WeightComputation"))

import torch

from compute_facd import load_mesh, load_weights
from localchamferdist import ChamferDistance
from localchamferdist import chamfer as _chamfer_backend
from localchamferdist.fachamfer import FeatureAwareChamferDistance

DEFAULT_CONFIG = ROOT / "configs" / "experiment.yaml"


def load_config(path: Path) -> dict:
    """Read configs/experiment.yaml. Returns an empty dict when it is absent."""
    if not path.is_file():
        return {}
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise SystemExit(
            "ERROR: PyYAML is required to read the configuration; run "
            "installation/install_dependencies.sh first."
        ) from exc
    with path.open() as f:
        return yaml.safe_load(f) or {}


def cfg_get(cfg: dict, section: str, key: str, default):
    return (cfg.get(section) or {}).get(key, default)


def select_device(requested: str) -> str:
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        print("CUDA requested but not available: falling back to CPU.")
        requested = "cpu"
    if requested == "cuda" and _chamfer_backend._C is None:
        print("localchamferdist._C is not built: falling back to CPU (scipy KD-tree).")
        requested = "cpu"
    return requested


def ensure_weights(gt_path: Path, weights_path: Path, cfg: dict) -> None:
    """Compute the curvature-based FACD weights of the ground truth."""
    if gt_path.suffix.lower() != ".obj":
        raise SystemExit(
            "ERROR: FACD weights can only be computed from an OBJ ground truth "
            "(with faces). Pass an existing weights file with --weights."
        )
    # Imported lazily so that using an existing weights file does not require
    # libigl (compute_weights.py reports its absence at import time).
    from compute_weights import compute_and_save_semantic_weights

    weights_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        compute_and_save_semantic_weights(
            str(gt_path),
            str(weights_path),
            baseline_weight=float(cfg_get(cfg, "weights", "baseline_weight", 1.0)),
            scale_factor=float(cfg_get(cfg, "weights", "scale_factor", 299.0)),
            gamma=float(cfg_get(cfg, "weights", "gamma", 2.0)),
            active_threshold=float(cfg_get(cfg, "weights", "active_threshold", 1e-5)),
            clamp_percentile=float(cfg_get(cfg, "weights", "clamp_percentile", 90.0)),
        )
    except RuntimeError as exc:
        raise SystemExit(
            f"ERROR: {exc}\nRun installation/install_dependencies.sh to install libigl."
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate one reconstruction with CD, FACD, HFACD and HFACD2."
    )
    parser.add_argument("--ground_truth", required=True,
                        help="Ground-truth mesh (.obj; faces are required to compute weights).")
    parser.add_argument("--reconstruction", required=True,
                        help="Reconstructed mesh (.obj or any format meshio can read, e.g. .ply).")
    parser.add_argument("--weights", default=None,
                        help="Per-vertex FACD weights of the ground truth (JSON). If omitted, "
                             "gt_curvature.json next to the ground truth is used, or computed.")
    parser.add_argument("--weights_out", default=None,
                        help="Where to write computed weights (default: next to the ground truth).")
    parser.add_argument("--recompute_weights", action="store_true",
                        help="Recompute the weights even if a weights file exists.")
    parser.add_argument("--output_csv", default=None,
                        help="Output CSV (default: results/evaluation.csv).")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="Experiment configuration (default: configs/experiment.yaml).")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default=None,
                        help="Defaults to evaluation.device in the configuration.")
    parser.add_argument("--method", default=None,
                        help="Method label for the CSV (default: reconstruction file stem).")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    rec_path = Path(args.reconstruction)
    if not gt_path.is_file():
        parser.error(f"ground truth not found: {gt_path}")
    if not rec_path.is_file():
        parser.error(f"reconstruction not found: {rec_path}")

    config_path = Path(args.config)
    cfg = load_config(config_path)
    if config_path.is_file():
        print(f"Config:         {config_path}")
    else:
        print(f"Config:         {config_path} (not found; using built-in defaults)")

    device = select_device(args.device or str(cfg_get(cfg, "evaluation", "device", "auto")))
    backend = "CUDA brute force" if device == "cuda" else "scipy KD-tree"
    output_csv = Path(args.output_csv) if args.output_csv else ROOT / "results" / "evaluation.csv"
    method = args.method or rec_path.stem

    # ------------------------------------------------------------
    # FACD weights of the ground truth
    # ------------------------------------------------------------
    weights_name = str(cfg_get(cfg, "weights", "computed_name", "gt_curvature.json"))
    weights_path = None
    if not args.recompute_weights:
        if args.weights:
            weights_path = Path(args.weights)
            if not weights_path.is_file():
                parser.error(f"weights file not found: {weights_path}")
        else:
            candidate = gt_path.resolve().parent / weights_name
            if candidate.is_file():
                weights_path = candidate
    if weights_path is None:
        weights_path = Path(args.weights_out) if args.weights_out else gt_path.resolve().parent / weights_name
        print(f"Computing FACD weights -> {weights_path}")
        ensure_weights(gt_path, weights_path, cfg)
    if not weights_path.is_file():
        parser.error(f"weights file not found: {weights_path}")

    # ------------------------------------------------------------
    # Load geometry and distances
    # ------------------------------------------------------------
    target = load_mesh(str(gt_path), device=device)
    source = load_mesh(str(rec_path), device=device)
    weights = load_weights(str(weights_path), target.shape[1], device=device)
    if weights is None:
        parser.error(f"could not read weights from {weights_path}")

    print(f"Ground truth:   {gt_path} ({target.shape[1]} points)")
    print(f"Reconstruction: {rec_path} ({source.shape[1]} points)")
    print(f"Weights:        {weights_path} ({weights.shape[1]} vertices, "
          f"range [{weights.min().item():.4f}, {weights.max().item():.4f}])")
    print(f"Device:         {device} ({backend})")

    cd = ChamferDistance()
    facd = FeatureAwareChamferDistance()
    with torch.no_grad():
        forward = cd(target, source, reverse=True, bidirectional=False, point_reduction="mean")
        backward = cd(target, source, reverse=False, bidirectional=False, point_reduction="mean")
        facd_forward = facd(target, source, weights_source=weights, reverse=True,
                            bidirectional=False, point_reduction="mean")
        facd_backward = facd(target, source, weights_source=weights, reverse=False,
                             bidirectional=False, point_reduction="mean")

    cd_val = 0.5 * (forward + backward)
    hcd = 2.0 * forward * backward / (forward + backward + 1e-8)
    hcd_2 = 2.0 * (1 + forward) * (1 + backward) / ((1 + forward) + (1 + backward)) - 1.0
    facd_val = 0.5 * (facd_forward + facd_backward)
    hfacd = 2.0 * facd_forward * facd_backward / (facd_forward + facd_backward + 1e-8)
    hfacd_2 = (2.0 * (1 + facd_forward) * (1 + facd_backward)
               / ((1 + facd_forward) + (1 + facd_backward)) - 1.0)

    values = {
        "cd": cd_val.item(),
        "hcd": hcd.item(),
        "hcd_2": hcd_2.item(),
        "facd": facd_val.item(),
        "hfacd": hfacd.item(),
        "hfacd_2": hfacd_2.item(),
    }
    for name, value in values.items():
        print(f"{name.upper():8s} = {value:.6f}")

    # ------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------
    row = {
        "ground_truth": str(gt_path),
        "reconstruction": str(rec_path),
        "method": method,
        "cd": f"{values['cd']:.9f}",
        "hcd": f"{values['hcd']:.9f}",
        "hcd_2": f"{values['hcd_2']:.9f}",
        "facd": f"{values['facd']:.9f}",
        "hfacd": f"{values['hfacd']:.9f}",
        "hfacd_2": f"{values['hfacd_2']:.9f}",
        "num_source_pts": source.shape[1],
        "num_target_pts": target.shape[1],
        "device": device,
        "weights": str(weights_path),
    }
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    print(f"Wrote {output_csv}")


if __name__ == "__main__":
    main()
