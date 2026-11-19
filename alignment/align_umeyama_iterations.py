"""
" Implements the Umeyama algorithm for estimating the optimal transformation form a camera
" point cloud to a ground truth camera point cloud, given known correspondences.
" (i. e., the camera indices are shared between GT and Reconstruction, but the 3D positions
" may be misaligned by an unknown Sim(3) transform).
" In this version, we perform iterative trimming by discarding the worst matched pairs until
" discarding a '1 - keep_ratio' percentage of the data.
" Supports COLMAP like .txt and .bin formats for cameras, as well as InstantNGP json format
" style].
Author: Cristián Llull (2026) with Gemini
"""
import argparse
import open3d as o3d
import numpy as np
import json
import sys
import os

try:
    from colmap_read_write_model import read_images_text, read_images_binary, qvec2rotmat
except ImportError:
    print("[ERROR] 'colmap_read_write_model.py' must be in the same directory.")
    sys.exit(1)

def load_cameras(file_path):
    """
    Parses camera centers from COLMAP (.txt, .bin) or custom JSON formats.
    Returns a dictionary mapping image names to their 3D optical centers.
    """
    cameras = {}
    
    if file_path.endswith(".json"):
        with open(file_path, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]
            
        for entry in data:
            name = entry["image"]
            ext = np.array(entry["extrinsic"])
            R = ext[:, :3]
            t = ext[:, 3].reshape(3, 1)
            C = -R.T @ t
            cameras[name] = C.squeeze()
            
    elif file_path.endswith(".txt"):
        imgs = read_images_text(file_path)
        for _, img in imgs.items():
            R = qvec2rotmat(img.qvec)
            t = img.tvec.reshape(3, 1)
            C = -R.T @ t
            cameras[img.name] = C.squeeze()
            
    elif file_path.endswith(".bin"):
        imgs = read_images_binary(file_path)
        for _, img in imgs.items():
            R = qvec2rotmat(img.qvec)
            t = img.tvec.reshape(3, 1)
            C = -R.T @ t
            cameras[img.name] = C.squeeze()
            
    else:
        raise ValueError(f"Unsupported camera file format: {file_path}")
        
    return cameras

def umeyama_sim3(X, Y):
    """
    Computes the optimal Sim(3) transformation (s, R, t) using standard Procrustes.
    Model: Y \approx s * (X @ R.T) + t
    """
    N, m = X.shape
    mu_X = X.mean(axis=0)
    mu_Y = Y.mean(axis=0)
    
    Xc = X - mu_X
    Yc = Y - mu_Y
    
    var_X = np.mean(np.sum(Xc**2, axis=1))
    Sigma = (Yc.T @ Xc) / N
    
    U, D, Vt = np.linalg.svd(Sigma)
    
    S = np.eye(m)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[-1, -1] = -1
        
    R = U @ S @ Vt
    s = np.trace(np.diag(D) @ S) / var_X
    t = mu_Y - s * (R @ mu_X)
    
    return s, R, t

def umeyama_sim3_robust(X, Y, names, keep_ratio=0.95):
    """
    Computes robust Sim(3) alignment by iteratively discarding the worst matched pairs.
    """
    N = len(X)
    num_to_drop = int(N * (1.0 - keep_ratio))
    print("Num to drop", num_to_drop)
    inlier_mask = np.ones(N, dtype=bool)
    
    print(f"[INFO] Initiating Robust Alignment. Target drop count: {num_to_drop} cameras ({(1-keep_ratio)*100:.1f}%).")
    
    for step in range(num_to_drop):
        # 1. Estimate transform with current inliers
        X_in = X[inlier_mask]
        Y_in = Y[inlier_mask]
        s, R, t = umeyama_sim3(X_in, Y_in)
        
        # 2. Compute errors for all points
        X_aligned = s * (X @ R.T) + t
        errors = np.linalg.norm(X_aligned - Y, axis=1) # Euclidean distance per point
        
        # 3. Find the maximum error AMONG CURRENT INLIERS
        # Set outlier errors to -1 so they aren't selected again
        errors_inliers = np.where(inlier_mask, errors, -1.0)
        worst_idx = np.argmax(errors_inliers)
        
        # 4. Discard the worst point
        inlier_mask[worst_idx] = False
        print(f"   [-] Step {step+1}/{num_to_drop}: Dropped '{names[worst_idx]}' (Residual: {errors[worst_idx]:.5f})")
        
    # Final alignment with remaining inliers
    X_final = X[inlier_mask]
    Y_final = Y[inlier_mask]
    s_final, R_final, t_final = umeyama_sim3(X_final, Y_final)
    
    return s_final, R_final, t_final, inlier_mask

def main():
    parser = argparse.ArgumentParser(description="Robust Sim(3) alignment with Iterative Trimming.")
    parser.add_argument("--gt_cams", required=True, help="Path to ground truth cameras (.txt, .bin, or .json)")
    parser.add_argument("--rec_cams", required=True, help="Path to reconstructed cameras (.txt, .bin, or .json)")
    parser.add_argument("--input_model", required=False, help="Reconstruction 3D model (.ply) to be transformed")
    parser.add_argument("--out_model", default="aligned_reconstruction_iterative.ply", help="Output path for the aligned model")
    parser.add_argument("--out_transform", default="T_rec_to_gt.txt", help="Path to save the 4x4 Sim(3) matrix")
    parser.add_argument("--keep_ratio", type=float, default=0.8, help="Fraction of cameras to keep (default: 0.8)")
    args = parser.parse_args()

    # --- 1. Load Cameras ---
    gt_dict = load_cameras(args.gt_cams)
    rec_dict = load_cameras(args.rec_cams)

    # --- 2. Match Correspondences ---
    shared_names = sorted(list(set(gt_dict.keys()) & set(rec_dict.keys())))
    if not shared_names:
        print("[ERROR] No common image names found between GT and Reconstruction!")
        sys.exit(1)
        
    X = np.array([rec_dict[name] for name in shared_names])
    Y = np.array([gt_dict[name] for name in shared_names])

    # --- 3. Compute Robust Alignment ---
    s, R, t, inlier_mask = umeyama_sim3_robust(X, Y, shared_names, keep_ratio=args.keep_ratio)

    # --- 4. Evaluate Final Error ---
    X_aligned = s * (X @ R.T) + t
    
    # Calculate RMSE only on the inliers
    rmse_inliers = np.sqrt(np.mean(np.sum((X_aligned[inlier_mask] - Y[inlier_mask])**2, axis=1)))
    # Calculate RMSE on ALL cameras for comparison
    rmse_all = np.sqrt(np.mean(np.sum((X_aligned - Y)**2, axis=1)))
    
    print("-" * 50)
    print(f"Final Inlier RMSE (optimized): {rmse_inliers:.8f}")
    print(f"Global RMSE (including drops): {rmse_all:.8f}")
    print(f"Estimated Optimal Scale (s):   {s:.8f}")
    print("-" * 50)

    # --- 5. Build 4x4 Transformation Matrix ---
    T = np.eye(4)
    T[:3, :3] = s * R
    T[:3, 3] = t

    np.savetxt(args.out_transform, T, fmt="%.8f")
    print(f"[INFO] Transform saved to {args.out_transform}")

    # --- 6. Apply to Geometry ---
    if args.input_model and os.path.exists(args.input_model):
        print(f"[INFO] Applying Sim(3) transformation to {args.input_model}...")
        
        geometry = o3d.io.read_triangle_mesh(args.input_model)
        is_mesh = len(geometry.triangles) > 0
        
        if not is_mesh:
            geometry = o3d.io.read_point_cloud(args.input_model)
        
        geometry.transform(T)
        
        if is_mesh and geometry.has_vertex_normals():
            geometry.compute_vertex_normals()
            o3d.io.write_geometry(args.out_model, geometry)
        else:
            o3d.io.write_point_cloud(args.out_model, geometry)
        
        print(f"[INFO] Aligned geometry saved successfully to {args.out_model}")


if __name__ == "__main__":
    main()