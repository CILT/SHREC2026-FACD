"""Build paper Table 4 (CD, FACD, HFACD, HFACD2 of the 8 reconstructions of
four objects) from the CSV written by compute_facd.py, and compare it with the
values printed in the paper (reference/table4_paper.csv).

Outputs, in --out_dir:
    table4.md          the table, best in bold, second best in italics, worst with *
    table4.tex         the same table as a LaTeX tabular
    table4_compare.csv computed vs. paper value for every cell

The check passes when every value matches the paper to its printed precision
(6 decimals) or within REL_TOLERANCE, and the best / second best / worst method
of every row is the same as in the paper. The relative tolerance absorbs the
float32 (CUDA) vs. float64 (KD-tree) nearest-neighbour arithmetic.
"""
import argparse
import csv
import os
import sys

METHODS = ["sam_sugar", "nerf_instantngp", "vggt_frame", "colmap",
           "neus", "vggt", "vggt_100k", "vggt_high_def"]
METRICS = [("cd", "CD"), ("facd", "FACD"), ("hfacd", "HFACD"), ("hfacd_2", "HFACD2")]
EXAMPLES = [
    ("90_1920x1080_relief_heightmap_5_one_face_wide", "Example 1: 5_one_face_wide (High-Frequency Relief)"),
    ("90_1920x1080_relief_heightmap_6_one_face_large", "Example 2: 6_one_face_large (High-Frequency Relief)"),
    ("90_1920x1080_relief_heightmap_3_one_face_large_pyramid", "Example 3: 3_one_face_large_pyramid (Complex Topology & Untextured Stone)"),
    ("90_1920x1080_relief_heightmap_1_all_wide_package", "Example 4: 1_all_wide_package (Straight and Curved Edges)"),
]
# The paper prints 6 decimals; allow one unit in the last place...
TOLERANCE = 1.01e-6
# ...or a 0.1% relative difference.
REL_TOLERANCE = 1e-3


def read_results(path):
    values = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            for metric, _ in METRICS:
                values[(row["experiment_id"], row["method"], metric)] = float(row[metric])
    return values


def read_reference(path):
    with open(path, newline="") as f:
        return {(r["experiment_id"], r["method"], r["metric"]): float(r["value"])
                for r in csv.DictReader(f)}


def ranks(row):
    """Index of the best, second best and worst value (lower is better)."""
    order = sorted((v, i) for i, v in enumerate(row) if v is not None)
    if not order:
        return None, None, None
    return order[0][1], order[1][1] if len(order) > 1 else None, order[-1][1]


def format_cells(row, style):
    best, second, worst = ranks(row)
    cells = []
    for i, v in enumerate(row):
        if v is None:
            cells.append("n/a")
            continue
        s = f"{v:.6f}"
        if style == "md":
            s = f"**{s}**" if i == best else f"_{s}_" if i == second else f"{s}*" if i == worst else s
        else:
            s = (f"\\textbf{{{s}}}" if i == best else f"\\underline{{{s}}}" if i == second
                 else f"{s}$^*$" if i == worst else s)
        cells.append(s)
    return cells


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="Build Table 4 of the paper from compute_facd.py results.")
    parser.add_argument("--results_csv", default=os.path.join(root, "results", "table4_distances.csv"))
    parser.add_argument("--reference_csv", default=os.path.join(root, "reference", "table4_paper.csv"))
    parser.add_argument("--out_dir", default=os.path.join(root, "results"))
    args = parser.parse_args()

    values = read_results(args.results_csv)
    reference = read_reference(args.reference_csv)
    os.makedirs(args.out_dir, exist_ok=True)

    md = ["# Table 4: CD and FACD of the eight reconstructions (lower is better)", "",
          "Best in **bold**, second best in _italics_, worst marked with *.", ""]
    tex = ["\\begin{tabular}{l" + "r" * len(METHODS) + "}", "\\hline",
           "Metric & " + " & ".join(m.replace("_", "\\_") for m in METHODS) + " \\\\", "\\hline"]
    for exp, title in EXAMPLES:
        md += [f"## {title}", "", "| Metric | " + " | ".join(METHODS) + " |",
               "|---" * (len(METHODS) + 1) + "|"]
        tex += [f"\\multicolumn{{{len(METHODS) + 1}}}{{c}}{{{title.replace('_', chr(92) + '_').replace('&', chr(92) + '&')}}} \\\\", "\\hline"]
        for metric, label in METRICS:
            row = [values.get((exp, m, metric)) for m in METHODS]
            md.append(f"| {label} | " + " | ".join(format_cells(row, "md")) + " |")
            tex.append(f"{label} & " + " & ".join(format_cells(row, "tex")) + " \\\\")
        md.append("")
        tex.append("\\hline")
    tex.append("\\end{tabular}")

    with open(os.path.join(args.out_dir, "table4.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(args.out_dir, "table4.tex"), "w") as f:
        f.write("\n".join(tex) + "\n")

    # ------------------------------------------------------------
    # Comparison with the published values
    # ------------------------------------------------------------
    n_exact, n_ok, n_bad, n_missing, max_rel = 0, 0, 0, 0, 0.0
    with open(os.path.join(args.out_dir, "table4_compare.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["experiment_id", "method", "metric", "computed", "paper", "abs_diff", "rel_diff", "ok"])
        for key, paper_value in sorted(reference.items()):
            computed = values.get(key)
            if computed is None:
                n_missing += 1
                writer.writerow(list(key) + ["", paper_value, "", "", False])
                continue
            diff = abs(computed - paper_value)
            rel = diff / abs(paper_value) if paper_value else 0.0
            exact = diff <= TOLERANCE
            ok = exact or rel <= REL_TOLERANCE
            if not exact:
                max_rel = max(max_rel, rel)
            n_exact += exact
            n_ok += ok
            n_bad += not ok
            writer.writerow(list(key) + [f"{computed:.9f}", f"{paper_value:.6f}", f"{diff:.3e}", f"{rel:.3e}", ok])
            if not ok:
                print(f"  MISMATCH {key}: computed {computed:.6f}, paper {paper_value:.6f}")

    # Same best / second best / worst method in every row?
    n_rank_bad = 0
    for exp, _ in EXAMPLES:
        for metric, label in METRICS:
            ours = ranks([values.get((exp, m, metric)) for m in METHODS])
            paper = ranks([reference.get((exp, m, metric)) for m in METHODS])
            if ours != paper:
                n_rank_bad += 1
                print(f"  RANKING DIFFERS {exp} {label}: "
                      f"computed {[METHODS[i] for i in ours]}, paper {[METHODS[i] for i in paper]}")

    print("\n".join(md))
    print(f"Compared {len(reference)} values with the paper:")
    print(f"  {n_exact} identical to the printed 6 decimals, {n_ok - n_exact} within "
          f"{REL_TOLERANCE:.1%} (largest relative difference among them {max_rel:.2e}), {n_bad} differ, {n_missing} missing.")
    print(f"  Best / second best / worst method identical in "
          f"{len(EXAMPLES) * len(METRICS) - n_rank_bad} of {len(EXAMPLES) * len(METRICS)} rows.")
    if n_bad or n_missing or n_rank_bad:
        print("RESULT: FAIL - the table does not match the paper.")
        sys.exit(1)
    print("RESULT: PASS - Table 4 of the paper is reproduced.")
    print(f"Tables written to {args.out_dir}/table4.md and table4.tex")


if __name__ == "__main__":
    main()
