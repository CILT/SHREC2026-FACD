#!/usr/bin/env bash
# Reproduce Table 4 of the paper (CD, FACD, HFACD and HFACD2 of the eight reconstructions
# of four objects). No parameters:
#
#   bash reproduce_table4.sh
#
# Steps: install (if needed) -> download data (if needed) -> compute the curvature-based FACD
# weights of every ground-truth mesh -> compute the distances -> build the table and compare it
# with the values printed in the paper. Outputs are written to ./results.
# Runtime: ~7 min on an 8-core CPU (plus ~2 min for install.sh), < 1 GB of RAM.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.env/bin/python"
DATA="$ROOT/data/SHREC2026_FACD_Table4"
RESULTS="$ROOT/results"

[[ -x "$PY" ]] || bash "$ROOT/install.sh"
bash "$ROOT/download_data.sh"
mkdir -p "$RESULTS"

echo "==> [1/3] Curvature-based FACD weights of the ground truths (paper Sec. 3.2.1)"
"$PY" "$ROOT/WeightComputation/compute_weights.py" --root_dir "$DATA" --overwrite
"$PY" "$ROOT/WeightComputation/compare_weights.py" --root_dir "$DATA"

echo "==> [2/3] CD, HCD, HCD2, FACD, HFACD, HFACD2 (paper Sec. 3.2.2)"
(cd "$ROOT/FACD_Evaluation" && "$PY" compute_facd.py --root_dir "$DATA" \
    --output_csv "$RESULTS/table4_distances.csv")

echo "==> [3/3] Table 4"
"$PY" "$ROOT/FACD_Evaluation/make_table4.py" \
    --results_csv "$RESULTS/table4_distances.csv" --out_dir "$RESULTS"
