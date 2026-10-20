"""Compute CD, HCD, HCD2, FACD, HFACD and HFACD2 (paper Sec. 3.2.2, Eqs. 7-12)
between every reconstruction and its ground truth.

Expected layout (one folder per object):

    <root_dir>/<experiment_id>/gt.obj               ground-truth mesh (target T)
    <root_dir>/<experiment_id>/gt_curvature.json    per-vertex FACD weights
                                                    (WeightComputation/compute_weights.py)
    <root_dir>/<experiment_id>/<reconstruction>     one file per method, see SOURCES

Results are written to a CSV with one row per (experiment_id, method).
"""
import argparse
import json, meshio
import os
import csv
import torch
from localchamferdist.fachamfer import FeatureAwareChamferDistance
from localchamferdist import ChamferDistance
from localchamferdist import chamfer as _chamfer_backend
from ResourceTracker import ResourceTracker


# Reconstruction file of each evaluated method (paper Sec. 4).
SOURCES = {
    "colmap": "colmap.ply",
    "neus": "NeuS_00140000.ply",
    "sam_sugar": "SAMplify_SuGaR.obj",
    "nerf_instantngp": "NeRF_InstantNGP.ply",
    "vggt_frame": "vggt_frame.ply",
    "vggt_100k": "vggt_sparse_100000_aligned.ply",
    "vggt": "vggt_sparse_aligned.ply",
    "vggt_high_def": "vggt_sparse_res1920_1000000_aligned.ply",
}


def load_mesh(mesh_path, device="cpu"):
    # Load mesh
    # Only pointcloud matters for Chamfer distance
    if mesh_path.lower().endswith(".obj"):
        verts_list = []
        with open(mesh_path, "r") as f:
            for line in f:
                if line.startswith("v "):   # vertex position only
                    _, x, y, z = line.strip().split()[:4]
                    verts_list.append([float(x), float(y), float(z)])
        verts = torch.tensor(verts_list, dtype=torch.float32, device=device)[None, :, :]
    else:
        # PLY and others are safe
        mesh = meshio.read(mesh_path)
        verts = torch.tensor(mesh.points, dtype=torch.float32, device=device)[None, :, :]  # Shape (1, P, 3)

    return verts


def load_weights(json_path, num_vertices, device="cpu"):
    """Load the curvature-based weights {"<vertex index>": weight} written by
    WeightComputation/compute_weights.py. Missing vertices get weight 1."""
    if json_path is None or not os.path.exists(json_path):
        return None

    with open(json_path) as f:
        vertex_data = json.load(f)

    weights = torch.tensor([
        float(vertex_data.get(str(i), 1.0)) for i in range(num_vertices)
    ], dtype=torch.float32, device=device)[None, :]  # Shape (1, P)

    return weights


if __name__ == "__main__":
    # ------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Compute Chamfer and Feature-Aware Chamfer Distances for SHREC experiments.")
    parser.add_argument("--root_dir", type=str, default="./gathered_objects", help="Root directory containing experiment folders.")
    parser.add_argument("--output_csv", type=str, default="SHREC_chamfer_facd.csv", help="Output CSV file to store results.")
    parser.add_argument("--weights_name", type=str, default="gt_curvature.json", help="Name of the weights JSON inside each experiment folder.")
    parser.add_argument("--device", type=str, default=None, choices=["cpu", "cuda"], help="Defaults to cuda when available.")
    args = parser.parse_args()
    ROOT_DIR = args.root_dir
    OUTPUT_CSV = args.output_csv

    DEVICE = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    if DEVICE == "cuda" and _chamfer_backend._C is None:
        print("localchamferdist._C is not built: falling back to CPU (KD-tree).")
        DEVICE = "cpu"
    backend = "CUDA brute force" if DEVICE == "cuda" else "scipy KD-tree"
    print(f"Device: {DEVICE} (nearest-neighbour backend: {backend})")

    tracker = ResourceTracker(DEVICE)

    # ------------------------------------------------------------
    # Initialize distances
    # ------------------------------------------------------------
    cd = ChamferDistance()
    facd = FeatureAwareChamferDistance()

    # ------------------------------------------------------------
    # CSV setup
    # ------------------------------------------------------------
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_CSV)), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)

        headers = [
            "experiment_id",
            "method",
            "cd",
            "hcd",
            "hcd_2",
            "facd",
            "hfacd",
            "hfacd_2",
            "num_source_pts",
            "num_target_pts"
        ]

        writer.writerow(headers)

        # --------------------------------------------------------
        # Traverse experiments
        # --------------------------------------------------------
        for exp_name in sorted(os.listdir(ROOT_DIR)):
            exp_dir = os.path.join(ROOT_DIR, exp_name)
            if not os.path.isdir(exp_dir):
                continue

            print(f"\n=== Processing {exp_name} ===")

            gt_obj = os.path.join(exp_dir, "gt.obj")
            gt_curvature_json = os.path.join(exp_dir, args.weights_name)

            if not (os.path.exists(gt_obj) and os.path.exists(gt_curvature_json)):
                print(f"  Skipping: missing gt.obj or {args.weights_name}")
                continue

            # ----------------------------------------------------
            # Load GT once (ground truth = Target points)
            # ----------------------------------------------------
            target_verts = load_mesh(gt_obj, device=DEVICE)
            num_target_pts = target_verts.shape[1]

            target_weights = load_weights(gt_curvature_json, num_target_pts, device=DEVICE)

            # ----------------------------------------------------
            # Compare with each reconstruction (sources)
            # ----------------------------------------------------
            for method, rel_path in SOURCES.items():
                source_path = os.path.join(exp_dir, rel_path)
                if not os.path.exists(source_path):
                    print(f"  [{method}] missing → skipped")
                    continue

                print(f"  [{method}] evaluating...")

                # Reconstructions are the Source points
                source_verts = load_mesh(source_path, device=DEVICE)
                num_source_pts = source_verts.shape[1]

                # forward: reconstruction -> GT (CD_FWD), backward: GT -> reconstruction (CD_BWD)
                tracker.start()
                forward = cd(
                    target_verts,
                    source_verts,
                    reverse=True,
                    bidirectional=False,
                    point_reduction="mean"
                )
                backward = cd(
                    target_verts,
                    source_verts,
                    reverse=False,
                    bidirectional=False,
                    point_reduction="mean"
                )
                cd_stats = tracker.stop()
                print(f"    Time taken cd: {cd_stats['wall_time_sec']:.2f}")

                # Same directions, weighted by the GT vertex weights (forward
                # uses the weight of the nearest GT vertex of each point)
                tracker.start()
                facd_forward = facd(
                    target_verts,
                    source_verts,
                    weights_source=target_weights,
                    reverse=True,
                    bidirectional=False,
                    point_reduction="mean"
                )
                facd_backward = facd(
                    target_verts,
                    source_verts,
                    weights_source=target_weights,
                    reverse=False,
                    bidirectional=False,
                    point_reduction="mean"
                )
                facd_stats = tracker.stop()
                print(f"    Time taken facd: {facd_stats['wall_time_sec']:.2f}")


                # ------------------------------
                # Unweighted CD, Harmonic CD and Harmonic 2 (Eqs. 8-10)
                # ------------------------------
                cd_val = 0.5 * (forward + backward)
                hcd = 2.0 * forward * backward / (forward + backward + 1e-8)
                hcd_2 = 2.0 * (1 + forward) * (1 + backward) / ((1 + forward) + (1 + backward)) - 1.0

                # ------------------------------
                # FACD, Harmonic FACD and Harmonic FACD 2 (Eq. 12)
                # ------------------------------
                facd_val = 0.5 * (facd_forward + facd_backward)
                hfacd = 2.0 * facd_forward * facd_backward / (facd_forward + facd_backward + 1e-8)
                hfacd_2 = 2.0 * (1 + facd_forward) * (1 + facd_backward) / ((1 + facd_forward) + (1 + facd_backward)) - 1.0

                writer.writerow([
                    exp_name,
                    method,

                    cd_val.item(),
                    hcd.item(),
                    hcd_2.item(),

                    facd_val.item(),
                    hfacd.item(),
                    hfacd_2.item(),

                    num_source_pts,
                    num_target_pts
                ])
                f.flush()
                print(f"    CD      = {cd_val.item():.6f}")
                print(f"    FACD    = {facd_val.item():.6f}")
                print(f"    HFACD   = {hfacd.item():.6f}")
                print(f"    HFACD_2 = {hfacd_2.item():.6f}\n")
