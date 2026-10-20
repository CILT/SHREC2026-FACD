"""Render the FACD weight map of the sculpted (front) face of a ground-truth mesh,
as in Figure 9 of the paper: flat background in black (weight 1), carvings and
edges in yellow (weight 300). The front face is detected automatically and
projected orthographically, so this is meant for the cuboid Primitives
(normal, large, wide, realistic), not for the Derivatives.

    python render_weights.py --obj gt.obj --weights gt_curvature.json --output weights.png
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_vertices(obj_path):
    verts = []
    with open(obj_path) as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
    return np.array(verts)


def front_axis(verts, weights):
    """Axis and side (+1/-1) where the high-weight vertices lie closest to the bounding box."""
    center = 0.5 * (verts.min(0) + verts.max(0))
    half = 0.5 * (verts.max(0) - verts.min(0))
    rel = ((verts[weights > np.percentile(weights, 95)] - center) / half).mean(0)
    axis = int(np.argmax(np.abs(rel)))
    return axis, 1.0 if rel[axis] > 0 else -1.0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render the FACD weights of the front face of a mesh.")
    parser.add_argument("--obj", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=1000, help="Output size in pixels (square).")
    parser.add_argument("--slab", type=float, default=0.1, help="Depth of the front slab, as a fraction of the extent.")
    args = parser.parse_args()

    verts = load_vertices(args.obj)
    with open(args.weights) as f:
        data = json.load(f)
    weights = np.array([data[str(i)] for i in range(len(verts))])

    axis, side = front_axis(verts, weights)
    depth = side * verts[:, axis]
    keep = depth > depth.max() - args.slab * np.ptp(verts[:, axis])
    u, v = [a for a in range(3) if a != axis]
    order = np.argsort(depth[keep])  # front-most points drawn last
    pts, w = verts[keep][order], weights[keep][order]

    dpi = 100
    fig = plt.figure(figsize=(args.size / dpi, args.size / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("black")
    marker = (72.0 * args.size / dpi / np.sqrt(len(pts))) ** 2 * 2.0
    ax.scatter(side * pts[:, u] if axis != 2 else pts[:, u], pts[:, v], c=w, s=marker,
               cmap="inferno", vmin=weights.min(), vmax=weights.max(), linewidths=0, rasterized=True)
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.savefig(args.output, dpi=dpi, facecolor="black")
    print(f"Wrote {args.output} ({keep.sum()} front vertices, axis {'xyz'[axis]}{'+' if side > 0 else '-'})")
