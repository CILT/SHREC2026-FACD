#!/usr/bin/env bash
# Install everything needed to run the FACD code on a vanilla Linux (x86_64) system.
#
#   bash install.sh          CPU only (default, enough to reproduce Table 4)
#   bash install.sh --cuda   also builds the CUDA nearest-neighbour extension used in the paper
#                            (needs an NVIDIA GPU and driver supporting CUDA 11.8)
#
# Nothing is installed system-wide and no root access is needed: a private Miniforge is
# downloaded to ./.miniforge and the Python environment is created in ./.env.
# Remove both folders to uninstall.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_DIR="$ROOT/.miniforge"
ENV_DIR="$ROOT/.env"
MINIFORGE_VERSION="24.11.3-2"
MINIFORGE_URL="https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/Miniforge3-${MINIFORGE_VERSION}-Linux-x86_64.sh"
TORCH_VERSION="2.7.1"

WITH_CUDA=0
for arg in "$@"; do
    case "$arg" in
        --cuda) WITH_CUDA=1 ;;
        -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

download() {  # download <url> <output file>
    if command -v wget >/dev/null 2>&1; then
        wget -q --show-progress -O "$2" "$1"
    elif command -v curl >/dev/null 2>&1; then
        curl -fL --progress-bar -o "$2" "$1"
    else
        echo "ERROR: neither wget nor curl is available."; exit 1
    fi
}

# ------------------------------------------------------------
# 1. Private Miniforge (conda)
# ------------------------------------------------------------
if [[ ! -x "$CONDA_DIR/bin/conda" ]]; then
    echo "==> Downloading Miniforge ${MINIFORGE_VERSION}"
    installer="$(mktemp --suffix=.sh)"
    download "$MINIFORGE_URL" "$installer"
    bash "$installer" -b -p "$CONDA_DIR"
    rm -f "$installer"
fi
# Called through its own python: the conda launcher's shebang breaks on long install paths.
CONDA=("$CONDA_DIR/bin/python" -m conda)

# ------------------------------------------------------------
# 2. Python environment
# ------------------------------------------------------------
if [[ ! -x "$ENV_DIR/bin/python" ]]; then
    echo "==> Creating the Python environment in $ENV_DIR"
    "${CONDA[@]}" create -y -q -p "$ENV_DIR" -c conda-forge python=3.10
fi
PIP="$ENV_DIR/bin/python -m pip"

echo "==> Installing Python packages"
if [[ $WITH_CUDA -eq 1 ]]; then
    $PIP install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cu118
else
    $PIP install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu
fi
$PIP install -r "$ROOT/requirements.txt"

# ------------------------------------------------------------
# 3. Optional: CUDA KNN extension (localchamferdist._C)
# ------------------------------------------------------------
if [[ $WITH_CUDA -eq 1 ]]; then
    echo "==> Installing the CUDA 11.8 toolkit and GCC 11 into the environment"
    "${CONDA[@]}" install -y -q -p "$ENV_DIR" -c conda-forge "gxx_linux-64=11" "gcc_linux-64=11" ninja
    "${CONDA[@]}" install -y -q -p "$ENV_DIR" -c "nvidia/label/cuda-11.8.0" cuda-nvcc cuda-cudart-dev cuda-libraries-dev

    echo "==> Building localchamferdist._C"
    (
        cd "$ROOT/FACD_Evaluation"
        export PATH="$ENV_DIR/bin:$PATH"
        export CUDA_HOME="$ENV_DIR"
        export CC="$ENV_DIR/bin/x86_64-conda-linux-gnu-gcc"
        export CXX="$ENV_DIR/bin/x86_64-conda-linux-gnu-g++"
        export FORCE_CUDA=1
        # Without a visible GPU at build time, compile for common architectures.
        export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-6.1;7.0;7.5;8.0;8.6}"
        "$ENV_DIR/bin/python" setup.py build_ext --inplace
    )
fi

# ------------------------------------------------------------
# 4. Check
# ------------------------------------------------------------
cd "$ROOT/FACD_Evaluation"
"$ENV_DIR/bin/python" - <<'EOF'
import igl, meshio, scipy, torch
from localchamferdist import chamfer
print(f"torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
print("Nearest-neighbour backend:",
      "CUDA extension" if chamfer._C is not None and torch.cuda.is_available() else "scipy KD-tree (CPU)")
EOF
echo "==> Installation complete. Run: bash reproduce_table4.sh"
