import argparse
import json, meshio
import torch
import os
import csv
import torch
from localchamferdist.fachamfer import FeatureAwareChamferDistance
from localchamferdist import ChamferDistance
from ResourceTracker import ResourceTracker


category_to_weight = {
    "corner": 100.0,
    "edge": 50.0,
    "flat_face": 1.0,
    "sculpted_face": 300.0,
    "sculpted_flat": 1.0,
}


def load_mesh(mesh_path, device="cpu"):
    # Load mesh
    # Only pointcloud matters for Chamfer distance
    # If json_path is None, no weights are loaded
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
    """Dynamically parses either string categories (Manual) or floats (Curvature)."""
    if json_path is None or not os.path.exists(json_path):
        return None
    
    # Load weights
    with open(json_path) as f:
        vertex_data = json.load(f)  # dict: {"0": "corner", ...}

    if isinstance(vertex_data.get("0"), (float, int)):
        # Curvature-based weights
        weights = torch.tensor([
            float(vertex_data.get(str(i), 1.0)) for i in range(num_vertices)
        ], dtype=torch.float32, device=device)[None, :]  # Shape (1, P)
    else:
        # Manual category-based weights
        weights = torch.tensor([
            category_to_weight.get(vertex_data.get(str(i), "default"), 1.0)
            for i in range(num_vertices)
        ], dtype=torch.float32, device=device)[None, :]  # Shape (1, P)
    
    return weights


if __name__ == "__main__":
    # ------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Compute Chamfer and Feature-Aware Chamfer Distances for SHREC experiments.")
    parser.add_argument("--root_dir", type=str, default="./gathered_objects", help="Root directory containing experiment folders.")
    parser.add_argument("--output_csv", type=str, default="SHREC_chamfer_facd.csv", help="Output CSV file to store results.")
    args = parser.parse_args()
    ROOT_DIR = args.root_dir
    OUTPUT_CSV = args.output_csv

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

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(DEVICE)

    tracker = ResourceTracker(DEVICE)

    # ------------------------------------------------------------
    # Initialize distances
    # ------------------------------------------------------------
    cd = ChamferDistance()
    facd = FeatureAwareChamferDistance()

    # ------------------------------------------------------------
    # CSV setup
    # ------------------------------------------------------------
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
            "facd_auto",
            "hfacd_auto",
            "hfacd_2_auto",
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
            gt_json = os.path.join(exp_dir, "gt.json")
            gt_curvature_json = os.path.join(exp_dir, "gt_curvature.json")

            if not (os.path.exists(gt_obj) and os.path.exists(gt_json) and os.path.exists(gt_curvature_json)):
                print("  Skipping: missing gt.obj or gt.json or gt_curvature.json")
                continue

            # ----------------------------------------------------
            # Load GT once (ground truth = Target points)
            # ----------------------------------------------------
            target_verts = load_mesh(gt_obj, device=DEVICE)
            num_target_pts = target_verts.shape[1]

            target_weights_manual = load_weights(gt_json, num_target_pts, device=DEVICE)
            target_weights_curvature = load_weights(gt_curvature_json, num_target_pts, device=DEVICE)

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

                # Forward time:
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

                tracker.start()
                facd_forward = facd(
                    target_verts,
                    source_verts,
                    weights_source=target_weights_manual,
                    reverse=True,
                    bidirectional=False,
                    point_reduction="mean"
                )
                facd_backward = facd(
                    target_verts,
                    source_verts,
                    weights_source=target_weights_manual,
                    reverse=False,
                    bidirectional=False,
                    point_reduction="mean"
                )
                facd_stats = tracker.stop()
                print(f"    Time taken facd: {facd_stats['wall_time_sec']:.2f}")


                # ------------------------------
                # Unweighted CD, Harmonic CD and Harmonic 2
                # ------------------------------
                cd_val = 0.5 * (forward + backward)
                hcd = 2.0 * forward * backward / (forward + backward + 1e-8)
                hcd_2 = 2.0 * (1 + forward) * (1 + backward) / ((1 + forward) + (1 + backward)) - 1.0
                
                # ------------------------------
                # Weighted CD, Harmonic Weighted CD and Harmonic Weighted CD 2
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
                print(f"    CD      = {cd_val.item():.6f}")
                print(f"    FACD = {facd_val.item():.6f}")
                print(f"    HFACD = {hfacd.item():.6f}\n")
                print(f"    HFACD_2 = {hfacd_2.item():.6f}\n")
