#!/usr/bin/env bash
# Download and unpack the evaluation subset needed to reproduce Table 4
# (~480 MB download, ~1 GB unpacked): ground-truth meshes, the FACD weights used
# in the paper and the eight reconstructions of four objects.
#
#   bash download/download_evaluation_subset.sh
#
# The archive name and its SHA-256 are read from download/SHA256SUMS.txt; the
# Zenodo record and the output directory are read from configs/experiment.yaml
# (data.zenodo_record, data.archive, data.root). All of them can be overridden:
#
#   SHREC_ZENODO_RECORD_ID=23584779 \
#   SHREC_DATA_ARCHIVE=/path/to/SHREC2026_FACD_Table4.tar.gz \
#       bash download/download_evaluation_subset.sh
#
# A direct URL can be used instead of the Zenodo record:
#
#   SHREC_DATA_URL=https://example.org/SHREC2026_FACD_Table4.tar.gz \
#       bash download/download_evaluation_subset.sh
#
# The full 616-object dataset has its own downloader:
#   bash download/download_full_dataset.sh <ZENODO_RECORD_ID_OR_DOI>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/configs/experiment.yaml"

# Defaults; configs/experiment.yaml and environment variables override them.
ZENODO_RECORD_ID="23584779"
ARCHIVE_NAME="SHREC2026_FACD_Table4.tar.gz"
DATA_ROOT="$ROOT/data/SHREC2026_FACD_Table4"
MANIFEST="$ROOT/download/SHA256SUMS.txt"
CONFIG_URL=""

# Read the record, archive name, data root and checksum manifest from
# configs/experiment.yaml when the Python environment is available (PyYAML is
# installed by installation/install_dependencies.sh).
if [[ -x "$ROOT/.env/bin/python" && -f "$CONFIG" ]]; then
    config_values="$("$ROOT/.env/bin/python" - "$CONFIG" <<'PY'
import shlex
import sys
import yaml

with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f) or {}
data = cfg.get("data") or {}
values = {
    "ZENODO_RECORD_ID": data.get("zenodo_record"),
    "ARCHIVE_NAME": data.get("archive"),
    "DATA_ROOT": data.get("root"),
    "MANIFEST": data.get("checksums"),
    "CONFIG_URL": data.get("url"),
}
for key, value in values.items():
    if value:
        print(f"{key}={shlex.quote(str(value))}")
PY
)" || { echo "ERROR: could not read $CONFIG"; exit 1; }
    eval "$config_values"
fi

# Environment variables take precedence over the config file.
ZENODO_RECORD_ID="${SHREC_ZENODO_RECORD_ID:-$ZENODO_RECORD_ID}"
ARCHIVE_NAME="${SHREC_ZENODO_FILE:-$ARCHIVE_NAME}"
DATA_ROOT="${SHREC_DATA_ROOT:-$DATA_ROOT}"
MANIFEST="${SHREC_SHA256SUMS:-$MANIFEST}"

# Resolve paths relative to the repository root.
[[ "$DATA_ROOT" = /* ]] || DATA_ROOT="$ROOT/$DATA_ROOT"
[[ "$MANIFEST" = /* ]] || MANIFEST="$ROOT/$MANIFEST"
DATA_DIR="$(dirname "$DATA_ROOT")"
NAME="$(basename "$DATA_ROOT")"

# Accept a bare record ID, a DOI (10.5281/zenodo.XXXX) or a Zenodo URL.
if [[ "$ZENODO_RECORD_ID" =~ zenodo\.([0-9]+) ]]; then
    ZENODO_RECORD_ID="${BASH_REMATCH[1]}"
elif [[ ! "$ZENODO_RECORD_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: could not extract a Zenodo record ID from: $ZENODO_RECORD_ID"
    exit 1
fi

for cmd in tar sha256sum awk; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: missing required command: $cmd"
        exit 1
    fi
done

expected_sha256() {  # expected_sha256 <filename>
    [[ -f "$MANIFEST" ]] || return 1
    awk -v file="$1" '
        $2 == file || $2 == "*" file { print tolower($1); found = 1; exit }
        END { exit found ? 0 : 1 }
    ' "$MANIFEST"
}

verify_archive() {  # verify_archive <archive>
    local archive="$1" expected actual
    if ! expected="$(expected_sha256 "$ARCHIVE_NAME")"; then
        echo "ERROR: no SHA-256 entry for $ARCHIVE_NAME in $MANIFEST"
        return 1
    fi
    actual="$(sha256sum "$archive" | awk '{ print tolower($1) }')"
    if [[ "$actual" != "$expected" ]]; then
        echo "ERROR: SHA-256 mismatch for $archive"
        echo "  expected: $expected"
        echo "  actual:   $actual"
        return 1
    fi
    echo "==> SHA-256 OK ($ARCHIVE_NAME)"
}

if [[ -f "$DATA_ROOT/README.txt" ]]; then
    echo "==> Data already in $DATA_ROOT"
    exit 0
fi
mkdir -p "$DATA_DIR"

archive="${SHREC_DATA_ARCHIVE:-$DATA_DIR/$ARCHIVE_NAME}"
if [[ -f "$archive" ]]; then
    if ! verify_archive "$archive"; then
        if [[ -n "${SHREC_DATA_ARCHIVE:-}" ]]; then
            echo "ERROR: the archive supplied with SHREC_DATA_ARCHIVE failed verification."
            exit 1
        fi
        echo "==> Removing the corrupt archive and downloading it again"
        rm -f "$archive"
    fi
fi

if [[ ! -f "$archive" ]]; then
    URL="${SHREC_DATA_URL:-${CONFIG_URL:-https://zenodo.org/records/${ZENODO_RECORD_ID}/files/${ARCHIVE_NAME}?download=1}}"
    echo "==> Downloading $URL"
    if command -v wget >/dev/null 2>&1; then
        if ! wget -q --show-progress -c -O "$archive.part" "$URL"; then
            echo "ERROR: download failed. Check that Zenodo record ${ZENODO_RECORD_ID} contains ${ARCHIVE_NAME}."
            exit 1
        fi
    elif command -v curl >/dev/null 2>&1; then
        if ! curl -fL --progress-bar -C - -o "$archive.part" "$URL"; then
            echo "ERROR: download failed. Check that Zenodo record ${ZENODO_RECORD_ID} contains ${ARCHIVE_NAME}."
            exit 1
        fi
    elif command -v python3 >/dev/null 2>&1; then
        if ! python3 -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$URL" "$archive.part"; then
            echo "ERROR: download failed. Check that Zenodo record ${ZENODO_RECORD_ID} contains ${ARCHIVE_NAME}."
            exit 1
        fi
    else
        echo "ERROR: neither wget, curl nor python3 is available."
        exit 1
    fi
    mv "$archive.part" "$archive"
    if ! verify_archive "$archive"; then
        rm -f "$archive"
        echo "ERROR: the downloaded archive does not match download/SHA256SUMS.txt."
        exit 1
    fi
fi

echo "==> Checking archive paths"
if ! tar -tzf "$archive" | awk '
    {
        path = $0
        if (path ~ /^\// || path ~ /(^|\/)\.\.(\/|$)/) {
            print "Unsafe archive path: " path > "/dev/stderr"
            bad = 1
        }
    }
    END { exit bad }
'; then
    echo "ERROR: unsafe or invalid archive: $archive"
    exit 1
fi

echo "==> Unpacking into $DATA_DIR"
tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$DATA_DIR"

if [[ ! -f "$DATA_ROOT/README.txt" ]]; then
    echo "ERROR: expected $DATA_ROOT/README.txt after extraction."
    exit 1
fi
echo "==> Data ready in $DATA_ROOT"
