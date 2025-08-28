#!/usr/bin/env bash
set -euo pipefail

# Batch-upload Asciinema .cast recordings to asciinema.org
# Usage:
#   bash scripts/upload_casts.sh [file1.cast ... | directory ...]

# Ensure asciinema CLI is available
if ! command -v asciinema >/dev/null 2>&1; then
    echo "Error: 'asciinema' not found in PATH. Please install Asciinema to continue." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 file1.cast [file2.cast ... | directory ...]" >&2
    exit 1
fi

upload_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        echo "Skipping '$file': not found or not a regular file." >&2
        return
    fi
    echo "Uploading '$file'..."
    if url=$(asciinema upload "$file"); then
        echo " -> Uploaded: $url"
    else
        echo " -> Failed to upload '$file'." >&2
    fi
}

# Iterate through provided arguments
for target in "$@"; do
    if [ -d "$target" ]; then
        shopt -s nullglob
        files=("$target"/*.cast)
        shopt -u nullglob
        if [ ${#files[@]} -eq 0 ]; then
            echo "No .cast files found in directory '$target'." >&2
            continue
        fi
        for f in "${files[@]}"; do
            upload_file "$f"
        done
    else
        upload_file "$target"
    fi
done