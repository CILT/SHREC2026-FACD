
#!/usr/bin/env bash

set -Eeuo pipefail

# =========================================================
# Configuration
# =========================================================

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <ZENODO_RECORD_ID_OR_DOI> [OUTPUT_DIRECTORY]"
    echo
    echo "Examples:"
    echo "  $0 12345678"
    echo "  $0 10.5281/zenodo.12345678"
    echo "  $0 https://zenodo.org/records/12345678 ./dataset"
    exit 1
fi

INPUT="${1:-10.5281/zenodo.23584779}"

# Extract the numerical Zenodo record ID.
if [[ "$INPUT" =~ ^[0-9]+$ ]]; then
    RECORD_ID="$INPUT"
elif [[ "$INPUT" =~ /records?/([0-9]+) ]]; then
    RECORD_ID="${BASH_REMATCH[1]}"
elif [[ "$INPUT" =~ zenodo\.([0-9]+) ]]; then
    RECORD_ID="${BASH_REMATCH[1]}"
else
    echo "ERROR: Could not extract a Zenodo record ID from: $INPUT"
    exit 1
fi

OUT_DIR="${2:-./zenodo_dataset_${RECORD_ID}}"

ARCHIVE_DIR="$OUT_DIR/archives"
EXTRACT_DIR="$OUT_DIR/extracted"

API_URL="https://zenodo.org/api/records/${RECORD_ID}"

# =========================================================
# Dependencies
# =========================================================

for CMD in curl jq tar gzip md5sum sha256sum awk stat; do
    if ! command -v "$CMD" >/dev/null 2>&1; then
        echo "ERROR: Missing dependency: $CMD"
        exit 1
    fi
done

mkdir -p "$ARCHIVE_DIR" "$EXTRACT_DIR"

echo "=================================================="
echo "Zenodo dataset downloader"
echo "=================================================="
echo "Record ID:       $RECORD_ID"
echo "API:             $API_URL"
echo "Output:          $OUT_DIR"
echo

# =========================================================
# Retrieve record metadata.
# =========================================================

METADATA="$OUT_DIR/record_metadata.json"

echo "[1/4] Retrieving Zenodo metadata..."

curl --fail --show-error --location \
     --retry 4 \
     --retry-all-errors \
     --connect-timeout 30 \
     "$API_URL" \
     --output "${METADATA}.tmp"

mv -- "${METADATA}.tmp" "$METADATA"

if ! jq -e '(.files | type) == "array"' "$METADATA" >/dev/null; then
    echo "ERROR: Invalid Zenodo record or missing files."
    exit 1
fi

ARCHIVE_COUNT=$(jq \
    '[.files[] | select((.key // "") | endswith(".tar.gz"))] | length' \
    "$METADATA")

if (( ARCHIVE_COUNT == 0 )); then
    echo "ERROR: No .tar.gz files found in this Zenodo record."
    exit 1
fi

echo "Found $ARCHIVE_COUNT compressed archives."

# =========================================================
# Checksum verification function.
# =========================================================

verify_checksum() {

    local FILE="$1"
    local CHECKSUM="$2"
    local ALGORITHM
    local EXPECTED
    local ACTUAL

    [[ -n "$CHECKSUM" ]] || return 2

    if [[ "$CHECKSUM" == *:* ]]; then
        ALGORITHM="${CHECKSUM%%:*}"
        EXPECTED="${CHECKSUM#*:}"
    else
        # Zenodo's traditional checksum format is MD5.
        ALGORITHM="md5"
        EXPECTED="$CHECKSUM"
    fi

    case "$ALGORITHM" in

        md5)
            ACTUAL=$(md5sum -- "$FILE" | awk '{print $1}')
            ;;

        sha256)
            ACTUAL=$(sha256sum -- "$FILE" | awk '{print $1}')
            ;;

        *)
            echo "Unsupported checksum algorithm: $ALGORITHM" >&2
            return 2
            ;;
    esac

    [[ "${ACTUAL,,}" == "${EXPECTED,,}" ]]
}

# =========================================================
# Download files.
# =========================================================

echo
echo "[2/4] Downloading files..."
echo

ARCHIVES=()

while IFS=$'\t' read -r KEY URL CHECKSUM SIZE; do

    [[ -n "$KEY" ]] || continue

    # Only accept simple filenames, not arbitrary paths.
    if [[ "$KEY" == */* || "$KEY" == "." || "$KEY" == ".." ]]; then
        echo "ERROR: Unexpected filename in Zenodo metadata: $KEY"
        exit 1
    fi

    DEST="$ARCHIVE_DIR/$KEY"
    PART="${DEST}.part"

    echo "------------------------------------------"
    echo "File: $KEY"

    # Skip files that have already been downloaded and
    # whose checksum is correct.
    if [[ -s "$DEST" && -n "$CHECKSUM" ]]; then
        if verify_checksum "$DEST" "$CHECKSUM"; then
            echo "[VERIFIED] Already downloaded."
        else
            echo "[WARNING] Existing file failed verification."
            rm -f -- "$DEST"
        fi
    fi

    if [[ ! -f "$DEST" ]]; then

        # Resume an interrupted download when possible.
        if [[ -s "$PART" ]]; then

            if [[ -n "$CHECKSUM" ]] &&
               verify_checksum "$PART" "$CHECKSUM"; then

                mv -- "$PART" "$DEST"

            else
                echo "[RESUMING] $KEY"

                if ! curl --fail --show-error --location \
                          --retry 4 \
                          --retry-all-errors \
                          --connect-timeout 30 \
                          --continue-at - \
                          --output "$PART" \
                          "$URL"; then

                    echo "[WARNING] Resume failed. Restarting download."
                    rm -f -- "$PART"

                    curl --fail --show-error --location \
                         --retry 4 \
                         --retry-all-errors \
                         --connect-timeout 30 \
                         --output "$PART" \
                         "$URL"
                fi
            fi

        else
            echo "[DOWNLOADING] $KEY"

            curl --fail --show-error --location \
                 --retry 4 \
                 --retry-all-errors \
                 --connect-timeout 30 \
                 --output "$PART" \
                 "$URL"
        fi

        # Validate expected file size.
        if [[ "$SIZE" =~ ^[0-9]+$ ]] && (( SIZE > 0 )); then

            ACTUAL_SIZE=$(stat -c '%s' -- "$PART")

            if (( ACTUAL_SIZE != SIZE )); then
                echo "ERROR: File size mismatch for $KEY"
                rm -f -- "$PART"
                exit 1
            fi
        fi

        # Validate Zenodo checksum.
        if [[ -n "$CHECKSUM" ]]; then

            if ! verify_checksum "$PART" "$CHECKSUM"; then
                echo "ERROR: Checksum verification failed for $KEY"
                rm -f -- "$PART"
                exit 1
            fi

            echo "[VERIFIED] Zenodo checksum OK."

        else
            echo "[WARNING] No checksum available for $KEY"
        fi

        mv -- "$PART" "$DEST"
    fi

    # Keep track of compressed archives.
    if [[ "$KEY" == *.tar.gz ]]; then
        ARCHIVES+=("$DEST")
    fi

    echo "[SUCCESS] $KEY"

done < <(
    jq -r '
        .files[]
        | select(
            ((.key // "") | endswith(".tar.gz"))
            or .key == "SHA256SUMS.txt"
            or .key == "README.md"
        )
        | [
            .key,
            (.links.self // ""),
            (.checksum // ""),
            ((.size // 0) | tostring)
          ]
        | @tsv
    ' "$METADATA"
)

# =========================================================
# Verify SHA256 manifest.
# =========================================================

echo
echo "[3/4] Verifying SHA256 manifest..."

if [[ -f "$ARCHIVE_DIR/SHA256SUMS.txt" ]]; then

    (
        cd "$ARCHIVE_DIR"
        sha256sum --check SHA256SUMS.txt
    )

    echo "[SUCCESS] SHA256 verification completed."

else
    echo "[WARNING] SHA256SUMS.txt not found."
    echo "Zenodo checksums were used instead."
fi

# =========================================================
# Validate and extract archives.
# =========================================================

echo
echo "[4/4] Extracting archives..."
echo

for ARCHIVE in "${ARCHIVES[@]}"; do

    NAME=$(basename "$ARCHIVE")

    echo "------------------------------------------"
    echo "[EXTRACTING] $NAME"

    # Inspect archive paths before extraction.
    if ! tar -tzf "$ARCHIVE" | awk '
        {
            path = $0

            if (path ~ /^\// || path ~ /(^|\/)\.\.(\/|$)/) {
                print "Unsafe archive path: " path > "/dev/stderr"
                bad = 1
            }
        }
        END {
            exit bad
        }
    '; then
        echo "ERROR: Unsafe or invalid archive: $NAME"
        exit 1
    fi

    # Extract without restoring original ownership or
    # permissions.
    tar --no-same-owner \
        --no-same-permissions \
        -xzf "$ARCHIVE" \
        -C "$EXTRACT_DIR"

    echo "[SUCCESS] Extracted $NAME"

done

# =========================================================
# Final summary.
# =========================================================

echo
echo "=================================================="
echo "DOWNLOAD AND EXTRACTION COMPLETED"
echo "=================================================="

echo
echo "Downloaded archives:"
ls -lh "$ARCHIVE_DIR"

echo
echo "Extracted directories:"
find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d -print

echo
echo "Dataset location:"
echo "$EXTRACT_DIR"

echo
echo "Metadata:"
echo "$METADATA"

echo
echo "Done."

