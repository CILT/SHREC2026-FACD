#!/usr/bin/env bash
# Reproduce Table 4 of the paper (CD, FACD, HFACD and HFACD2 of the eight
# reconstructions of four objects). No parameters:
#
#   bash scripts/reproduce_table_04.sh
#
# Steps: install (if needed) -> download the evaluation subset (if needed) ->
# compute the curvature-based FACD weights of every ground-truth mesh ->
# compute the distances -> build the table and compare it with the values
# printed in the paper. Outputs are written to ./results.
# Runtime: ~7 min on an 8-core CPU (plus ~2 min for installation), < 1 GB of RAM.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.env/bin/python"
CONFIG="$ROOT/configs/experiment.yaml"

[[ -x "$PY" ]] || bash "$ROOT/installation/install_dependencies.sh"
[[ -f "$CONFIG" ]] || { echo "ERROR: configuration not found: $CONFIG"; exit 1; }

# Read the experiment configuration. PyYAML is installed by installation/.
config_values="$("$PY" - "$CONFIG" <<'PY'
import shlex
import sys
import yaml

with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f) or {}
data = cfg.get("data") or {}
weights = cfg.get("weights") or {}
evaluation = cfg.get("evaluation") or {}
results = cfg.get("results") or {}
values = {
    "CFG_DATA_ROOT": data.get("root", "data/SHREC2026_FACD_Table4"),
    "CFG_RESULTS_DIR": results.get("dir", "results"),
    "CFG_WEIGHTS_NAME": weights.get("computed_name", "gt_curvature.json"),
    "CFG_PAPER_WEIGHTS_NAME": weights.get("paper_name", "gt_curvature_paper.json"),
    "CFG_BASELINE_WEIGHT": weights.get("baseline_weight", 1.0),
    "CFG_SCALE_FACTOR": weights.get("scale_factor", 299.0),
    "CFG_GAMMA": weights.get("gamma", 2.0),
    "CFG_CLAMP_PERCENTILE": weights.get("clamp_percentile", 90.0),
    "CFG_ACTIVE_THRESHOLD": weights.get("active_threshold", 1.0e-5),
    "CFG_DEVICE": evaluation.get("device", "auto"),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(str(value))}")
PY
)" || { echo "ERROR: could not read $CONFIG"; exit 1; }
eval "$config_values"

if [[ "$CFG_DATA_ROOT" = /* ]]; then DATA="$CFG_DATA_ROOT"; else DATA="$ROOT/$CFG_DATA_ROOT"; fi
if [[ "$CFG_RESULTS_DIR" = /* ]]; then RESULTS="$CFG_RESULTS_DIR"; else RESULTS="$ROOT/$CFG_RESULTS_DIR"; fi

DEVICE_ARGS=()
case "$CFG_DEVICE" in
    cpu|cuda) DEVICE_ARGS=(--device "$CFG_DEVICE") ;;
    auto) ;;
    *) echo "ERROR: evaluation.device must be auto, cpu or cuda (got: $CFG_DEVICE)"; exit 1 ;;
esac

bash "$ROOT/download/download_evaluation_subset.sh"
mkdir -p "$RESULTS"

echo "==> [1/3] Curvature-based FACD weights of the ground truths (paper Sec. 3.2.1)"
"$PY" "$ROOT/WeightComputation/compute_weights.py" --root_dir "$DATA" --overwrite \
    --output_name "$CFG_WEIGHTS_NAME" \
    --baseline_weight "$CFG_BASELINE_WEIGHT" \
    --scale_factor "$CFG_SCALE_FACTOR" \
    --gamma "$CFG_GAMMA" \
    --clamp_percentile "$CFG_CLAMP_PERCENTILE" \
    --active_threshold "$CFG_ACTIVE_THRESHOLD"

"$PY" "$ROOT/WeightComputation/compare_weights.py" --root_dir "$DATA" \
    --computed "$CFG_WEIGHTS_NAME" --reference "$CFG_PAPER_WEIGHTS_NAME"

echo "==> [2/3] CD, HCD, HCD2, FACD, HFACD, HFACD2 (paper Sec. 3.2.2)"
(cd "$ROOT/FACD_Evaluation" && "$PY" compute_facd.py --root_dir "$DATA" \
    --weights_name "$CFG_WEIGHTS_NAME" \
    --output_csv "$RESULTS/table4_distances.csv" "${DEVICE_ARGS[@]}")

echo "==> [3/3] Table 4"
"$PY" "$ROOT/FACD_Evaluation/make_table4.py" \
    --results_csv "$RESULTS/table4_distances.csv" --out_dir "$RESULTS"
