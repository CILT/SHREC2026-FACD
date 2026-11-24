#!/usr/bin/env bash
# Reproduce Figure 1 of the paper, the teaser image in README.md: the FACD
# weight map of the front face of relief 1, one_face.
#
#   bash scripts/reproduce_figure_01.sh
#
# The mesh and its weights are included in the repository as
# sample/figure_01.tar.gz (~13 MB compressed, ~76 MB extracted), so the figure
# can be reproduced without the full dataset or a larger data download. The
# script extracts the archive to a temporary directory and removes it on exit.
#
# Alternative sources, in order:
#   1. $SHREC_FULL_DATASET/<object>.obj
#   2. $SHREC_FULL_DATASET/One_face_primitives/<object>.obj
#   3. <repo>/dataset/3D_ground_truth_dataset/One_face_primitives/<object>.obj
#   4. data/SHREC2026_FACD_Table4/figure_01/figure_01.obj
#   5. data/SHREC2026_FACD_Table4/<object>/gt.obj
# If none is available, it renders 5_one_face_wide from the evaluation subset
# and warns that this is an equivalent figure, not the README image.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${SHREC_PYTHON:-$ROOT/.env/bin/python}"
CONFIG="$ROOT/configs/experiment.yaml"
SAMPLE_ARCHIVE="$ROOT/sample/figure_01.tar.gz"

[[ -x "$PY" ]] || bash "$ROOT/installation/install_dependencies.sh"
[[ -f "$CONFIG" ]] || { echo "ERROR: configuration not found: $CONFIG"; exit 1; }

config_values="$("$PY" - "$CONFIG" <<'PY'
import shlex
import sys
import yaml

with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f) or {}
data = cfg.get("data") or {}
figure = cfg.get("figure") or {}
values = {
    "CFG_DATA_ROOT": data.get("root", "data/SHREC2026_FACD_Table4"),
    "CFG_FIGURE_OBJECT": figure.get("object", "90_1920x1080_relief_heightmap_1_one_face"),
    "CFG_FALLBACK_OBJECT": figure.get("fallback_object", "90_1920x1080_relief_heightmap_5_one_face_wide"),
    "CFG_FIGURE_OUTPUT": figure.get("output", "results/figure_01.png"),
    "CFG_FIGURE_SIZE": figure.get("size_px", 250),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(str(value))}")
PY
)" || { echo "ERROR: could not read $CONFIG"; exit 1; }
eval "$config_values"

if [[ "$CFG_DATA_ROOT" = /* ]]; then DATA="$CFG_DATA_ROOT"; else DATA="$ROOT/$CFG_DATA_ROOT"; fi
if [[ "$CFG_FIGURE_OUTPUT" = /* ]]; then OUTPUT="$CFG_FIGURE_OUTPUT"; else OUTPUT="$ROOT/$CFG_FIGURE_OUTPUT"; fi
mkdir -p "$(dirname "$OUTPUT")"

TMPDIR_FIG=""
cleanup() {
    if [[ -n "$TMPDIR_FIG" ]]; then
        rm -rf "$TMPDIR_FIG"
    fi
}
trap cleanup EXIT

OBJ=""
WEIGHTS=""
EXACT=0

# ------------------------------------------------------------
# 1. Figure 1 sample included in the repository.
# ------------------------------------------------------------
if [[ -f "$SAMPLE_ARCHIVE" ]]; then
    if ! tar -tzf "$SAMPLE_ARCHIVE" | awk '
        {
            path = $0
            if (path ~ /^\// || path ~ /(^|\/)\.\.(\/|$)/) {
                print "Unsafe archive path: " path > "/dev/stderr"
                bad = 1
            }
        }
        END { exit bad }
    '; then
        echo "ERROR: unsafe or invalid sample archive: $SAMPLE_ARCHIVE"
        exit 1
    fi
    TMPDIR_FIG="$(mktemp -d)"
    tar --no-same-owner --no-same-permissions -xzf "$SAMPLE_ARCHIVE" -C "$TMPDIR_FIG"
    if [[ -f "$TMPDIR_FIG/figure_01/figure_01.obj" && \
          -f "$TMPDIR_FIG/figure_01/figure_01_curvature.json" ]]; then
        OBJ="$TMPDIR_FIG/figure_01/figure_01.obj"
        WEIGHTS="$TMPDIR_FIG/figure_01/figure_01_curvature.json"
        EXACT=1
    else
        echo "WARNING: $SAMPLE_ARCHIVE does not contain the expected figure_01 files."
    fi
fi

# ------------------------------------------------------------
# 2-3. Exact object from the full dataset (author-side).
# ------------------------------------------------------------
if [[ -z "$OBJ" && -n "${SHREC_FULL_DATASET:-}" ]]; then
    for candidate in "$SHREC_FULL_DATASET/$CFG_FIGURE_OBJECT.obj" \
                     "$SHREC_FULL_DATASET/One_face_primitives/$CFG_FIGURE_OBJECT.obj"; do
        weights="${candidate%.obj}_curvature.json"
        if [[ -f "$candidate" && -f "$weights" ]]; then
            OBJ="$candidate"; WEIGHTS="$weights"; EXACT=1; break
        fi
    done
fi
if [[ -z "$OBJ" ]]; then
    candidate="$ROOT/dataset/3D_ground_truth_dataset/One_face_primitives/$CFG_FIGURE_OBJECT.obj"
    weights="${candidate%.obj}_curvature.json"
    if [[ -f "$candidate" && -f "$weights" ]]; then
        OBJ="$candidate"; WEIGHTS="$weights"; EXACT=1
    fi
fi

# ------------------------------------------------------------
# 4-5. Exact object from the evaluation subset (if added there).
# ------------------------------------------------------------
if [[ -z "$OBJ" ]]; then
    bash "$ROOT/download/download_evaluation_subset.sh"
    if [[ -f "$DATA/figure_01/figure_01.obj" && -f "$DATA/figure_01/figure_01_curvature.json" ]]; then
        OBJ="$DATA/figure_01/figure_01.obj"
        WEIGHTS="$DATA/figure_01/figure_01_curvature.json"
        EXACT=1
    elif [[ -f "$DATA/$CFG_FIGURE_OBJECT/gt.obj" && -f "$DATA/$CFG_FIGURE_OBJECT/gt_curvature_paper.json" ]]; then
        OBJ="$DATA/$CFG_FIGURE_OBJECT/gt.obj"
        WEIGHTS="$DATA/$CFG_FIGURE_OBJECT/gt_curvature_paper.json"
        EXACT=1
    fi
fi

# ------------------------------------------------------------
# Fallback: a Primitive that is in the evaluation subset today.
# ------------------------------------------------------------
if [[ -z "$OBJ" ]]; then
    if [[ -f "$DATA/$CFG_FALLBACK_OBJECT/gt.obj" && -f "$DATA/$CFG_FALLBACK_OBJECT/gt_curvature_paper.json" ]]; then
        OBJ="$DATA/$CFG_FALLBACK_OBJECT/gt.obj"
        WEIGHTS="$DATA/$CFG_FALLBACK_OBJECT/gt_curvature_paper.json"
        echo "WARNING: the Figure 1 object ($CFG_FIGURE_OBJECT) is not available."
        echo "         Rendering $CFG_FALLBACK_OBJECT instead; this is NOT the README image."
    else
        echo "ERROR: could not find the Figure 1 object $CFG_FIGURE_OBJECT."
        echo "       The repository sample sample/figure_01.tar.gz is missing or incomplete,"
        echo "       and the evaluation subset does not contain the object either."
        exit 1
    fi
fi

echo "==> Rendering FACD weights"
echo "    mesh:    $OBJ"
echo "    weights: $WEIGHTS"
echo "    output:  $OUTPUT (${CFG_FIGURE_SIZE}x${CFG_FIGURE_SIZE} px)"
"$PY" "$ROOT/WeightComputation/render_weights.py" \
    --obj "$OBJ" --weights "$WEIGHTS" --output "$OUTPUT" --size "$CFG_FIGURE_SIZE"

if [[ $EXACT -eq 1 && "$CFG_FIGURE_SIZE" == "250" ]]; then
    "$PY" - "$OUTPUT" "$ROOT/docs/teaser_250x250.png" <<'PY'
import sys

import numpy as np

try:
    from PIL import Image
except ImportError:
    print("RESULT: SKIPPED - Pillow is not installed; cannot compare images.")
    sys.exit(0)

out = np.asarray(Image.open(sys.argv[1]).convert("RGB"), dtype=int)
ref = np.asarray(Image.open(sys.argv[2]).convert("RGB"), dtype=int)
if out.shape != ref.shape:
    print(f"RESULT: WARNING - output is {out.shape}, reference is {ref.shape}")
    sys.exit(0)
diff = np.abs(out - ref)
mean = diff.mean()
identical = float(np.mean(np.all(out == ref, axis=2)) * 100)
if identical == 100.0:
    print("RESULT: PASS - figure 01 is pixel-identical to docs/teaser_250x250.png")
elif mean < 0.5 and identical > 99.0:
    print(f"RESULT: PASS (within tolerance) - {identical:.2f}% pixels identical, "
          f"mean absolute difference {mean:.3f}")
else:
    print(f"RESULT: WARNING - {identical:.2f}% pixels identical, "
          f"mean absolute difference {mean:.3f}")
PY
elif [[ $EXACT -eq 0 ]]; then
    echo "WARNING: figure rendered from the fallback object, so it differs from"
    echo "         docs/teaser_250x250.png by design."
fi
