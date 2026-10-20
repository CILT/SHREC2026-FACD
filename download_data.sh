#!/usr/bin/env bash
# Download and unpack the evaluation subset needed for Table 4 (~480 MB download, ~1 GB unpacked):
# ground-truth meshes, FACD weights used in the paper and the eight reconstructions of four objects.
#
#   bash download_data.sh
#
# To use an archive that is already on disk:  SHREC_DATA_ARCHIVE=/path/to/SHREC2026_FACD_Table4.tar.gz bash download_data.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$ROOT/data"
NAME="SHREC2026_FACD_Table4"
DATA_URL="TODO_DATA_URL/${NAME}.tar.gz"
SHA256="1bf49c95115db49860cd95222e6509bcc08157b04914ee50788dd83e8d83a336"

if [[ -f "$DATA_DIR/$NAME/README.txt" ]]; then
    echo "==> Data already in $DATA_DIR/$NAME"
    exit 0
fi
mkdir -p "$DATA_DIR"

archive="${SHREC_DATA_ARCHIVE:-$DATA_DIR/$NAME.tar.gz}"
if [[ ! -f "$archive" ]]; then
    echo "==> Downloading $DATA_URL"
    if command -v wget >/dev/null 2>&1; then
        wget -q --show-progress -O "$archive.part" "$DATA_URL"
    else
        curl -fL --progress-bar -o "$archive.part" "$DATA_URL"
    fi
    mv "$archive.part" "$archive"
fi

echo "==> Verifying checksum"
echo "$SHA256  $archive" | sha256sum -c -

echo "==> Unpacking into $DATA_DIR"
tar -xzf "$archive" -C "$DATA_DIR"
echo "==> Data ready in $DATA_DIR/$NAME"
