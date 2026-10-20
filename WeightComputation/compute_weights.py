"""This script provides a robust method for computing semantic weights based
on curvature for 3D meshes. It reads OBJ files, computes principal curvatures
using libigl, applies a smart clamping and normalization strategy

This is the version used to generate the curvature-based weights for all
meshes. It includes a purification step to handle non-manifold geometry and
outliers, ensuring that the resulting weights are meaningful and stable across
a wide variety of meshes. The script also includes a batch processing function
to handle multiple meshes in a directory structure."""
import argparse
import os
import json
import numpy as np
import scipy.spatial
import time
import multiprocessing

try:
    import igl
    HAS_IGL = True
except ImportError:
    HAS_IGL = False
    print("ERROR: libigl is strictly required for this exact methodology.")
    
def compute_and_save_semantic_weights(
    obj_path: str,
    output_path: str,
    baseline_weight: float = 1.0,
    scale_factor: float = 299.0,
    gamma: float = 2.0
) -> None:
    if not os.path.exists(obj_path):
        raise FileNotFoundError(f"OBJ file not found at: {obj_path}")
        
    print(f"\n--- Processing: {os.path.basename(os.path.dirname(obj_path))} / {os.path.basename(obj_path)} ---")
    start_time = time.time()
    
    # ---------------------------------------------------------
    # 1. EXACT CUSTOM READING APPROACH 
    # ---------------------------------------------------------
    verts_list = []
    faces_list = []
    
    with open(obj_path, "r") as f_obj:
        for line in f_obj:
            if line.startswith("v "):
                _, x, y, z = line.strip().split()[:4]
                verts_list.append([float(x), float(y), float(z)])
                
            elif line.startswith("f "): 
                parts = line.strip().split()[1:]
                face = [int(p.split('/')[0]) - 1 for p in parts]
                if len(face) == 3:
                    faces_list.append(face)
                elif len(face) == 4: 
                    faces_list.append([face[0], face[1], face[2]])
                    faces_list.append([face[0], face[2], face[3]])
                elif len(face) > 4:  
                    for i in range(1, len(face) - 1):
                        faces_list.append([face[0], face[i], face[i+1]])

    v_orig = np.array(verts_list, dtype=np.float64)
    f_orig = np.array(faces_list, dtype=np.int64)
    num_orig_vertices = len(v_orig)
    
    # ---------------------------------------------------------
    # 2. VIRTUAL WELDING & GEOMETRIC PURIFICATION
    # ---------------------------------------------------------
    v_rounded = np.round(v_orig, decimals=5)
    v_unique, inverse_indices = np.unique(v_rounded, axis=0, return_inverse=True)
    f_unique = inverse_indices[f_orig]
    
    # FILTER 1: Index-based degenerates
    valid_mask = (f_unique[:, 0] != f_unique[:, 1]) & \
                 (f_unique[:, 1] != f_unique[:, 2]) & \
                 (f_unique[:, 2] != f_unique[:, 0])
    f_clean = f_unique[valid_mask]

    # FILTER 2: Area-based degenerates (Collinear vertices)
    v0 = v_unique[f_clean[:, 0]]
    v1 = v_unique[f_clean[:, 1]]
    v2 = v_unique[f_clean[:, 2]]
    areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    f_clean = f_clean[areas > 1e-8]
    
    # FILTER 3: Remove Duplicate Faces (Fixes Cone/Pyramid Non-Manifold Apex!)
    f_sorted = np.sort(f_clean, axis=1)
    _, unique_face_mask = np.unique(f_sorted, axis=0, return_index=True)
    f_clean = f_clean[unique_face_mask]
    
    # FILTER 4: Remove orphaned vertices
    used_vertex_indices = np.unique(f_clean)
    v_clean = v_unique[used_vertex_indices]
    
    old_to_new = np.full(len(v_unique), -1, dtype=np.int64)
    old_to_new[used_vertex_indices] = np.arange(len(used_vertex_indices))
    f_clean = old_to_new[f_clean]

    print(f"Purification: Removed {len(f_unique) - len(f_clean)} bad faces (index/area limits).")
    print(f"Purification: Hid {len(v_unique) - len(v_clean)} orphaned vertices.")

    # ---------------------------------------------------------
    # 3. COMPUTE CURVATURE 
    # ---------------------------------------------------------
    if not HAS_IGL:
        raise RuntimeError("libigl not found. Cannot proceed.")

    curvature_results = igl.principal_curvature(v_clean, f_clean)
    k1 = curvature_results[2]
    k2 = curvature_results[3]
    raw_metric_clean = np.sqrt((k1**2 + k2**2) / 2.0)
    
    # Rebuild original arrays
    raw_metric_unique = np.zeros(len(v_unique), dtype=np.float64)
    raw_metric_unique[used_vertex_indices] = raw_metric_clean
    raw_metric = raw_metric_unique[inverse_indices]

    # ---------------------------------------------------------
    # 4. SMART CLAMPING (Feature-Active Percentiles)
    # ---------------------------------------------------------
    raw_metric = np.nan_to_num(raw_metric, nan=0.0, posinf=0.0, neginf=0.0)

    # Only calculate percentiles on the actual carvings, ignoring flat background rock
    active_curvatures = raw_metric[raw_metric > 1e-5]
    if len(active_curvatures) > 0:
        p_upper = np.percentile(active_curvatures, 90)
    else:
        p_upper = 1e-5

    p_lower = 0.0
    raw_metric_clamped = np.clip(raw_metric, p_lower, p_upper)
    
    metric_range = p_upper - p_lower
    if metric_range < 1e-8:
        normalized_metric = np.zeros_like(raw_metric_clamped)
    else:
        normalized_metric = (raw_metric_clamped - p_lower) / metric_range

    # ---------------------------------------------------------
    # 5. SCALING AND EXPORT
    # ---------------------------------------------------------
    enhanced_metric = np.power(normalized_metric, gamma)
    weights = baseline_weight + (scale_factor * enhanced_metric)
    weights = np.clip(weights, a_min=baseline_weight, a_max=None)

    weight_map = {str(idx): round(float(w), 4) for idx, w in enumerate(weights)}
    
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(weight_map, file, separators=(',', ':'))
        
    print(f"Export completed in {time.time() - start_time:.2f}s.")
    print(f"Max Clamped (300): {np.sum(weights >= 299.99)} vertices.")
    print(f"\n--- Final Weight Stats ---")
    print(f"Min Weight:  {np.min(weights):.4f}")
    print(f"Max Weight:  {np.max(weights):.4f}")
    print(f"Mean Weight: {np.mean(weights):.4f}")


def process_all_directories(root_directory: str, output_name: str = "gt_curvature.json", overwrite: bool = False):
    if not os.path.exists(root_directory):
        print(f"Error: The directory '{root_directory}' does not exist.")
        return 1

    print(f"Starting batch process in: {root_directory}")
    print("===================================================")
    
    success_count = 0
    fail_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_directory):
        if "gt.obj" in filenames:
            obj_path = os.path.join(dirpath, "gt.obj")
            json_output_path = os.path.join(dirpath, output_name)
            
            if os.path.exists(json_output_path) and not overwrite:
                print(f"Skipping {os.path.basename(dirpath)} - already exists.")
                continue
                
            # Process Isolation: Protects the main loop from C++ Segfaults
            p = multiprocessing.Process(
                target=compute_and_save_semantic_weights,
                args=(obj_path, json_output_path, 1.0, 299.0, 2.0)
            )
            p.start()
            p.join() # Wait for the sub-process to finish
            
            if p.exitcode == 0:
                success_count += 1
            else:
                print(f"!!! CRITICAL FAILED on {dirpath} !!!")
                print(f"(C++ backend crashed/segfaulted. Sub-process killed. Continuing to next mesh...)")
                fail_count += 1

    print("\n===================================================")
    print("BATCH PROCESSING COMPLETE")
    print(f"Successfully processed: {success_count} meshes.")
    if fail_count > 0:
        print(f"Skipped due to critical C++ failure: {fail_count} meshes.")
    return fail_count


if __name__ == "__main__":
    # Ensure multiprocessing works cleanly on all platforms
    multiprocessing.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser(description="Compute curvature-based semantic weights for 3D meshes.")
    parser.add_argument("--root_dir", type=str, default="./gathered_objects", help="Root directory containing experiment folders.")
    parser.add_argument("--output_name", type=str, default="gt_curvature.json", help="Name of the weights JSON written next to each gt.obj.")
    parser.add_argument("--overwrite", action="store_true", help="Recompute weights even if the JSON already exists.")
    args = parser.parse_args() 
    ROOT_DIR = args.root_dir
    failed = process_all_directories(ROOT_DIR, args.output_name, args.overwrite)
    raise SystemExit(1 if failed else 0)