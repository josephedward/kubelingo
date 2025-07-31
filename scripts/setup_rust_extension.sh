#!/usr/bin/env bash
set -euo pipefail

print_usage() {
  cat <<EOF
Usage: $(basename "$0") [--repo-dir DIR] [--install-dir DIR] [--config FILE]
Build and install the Kubelingo Rust extension and update configuration.

Options:
  --repo-dir DIR     Path to the kubelingo git repository (default: current directory)
  --install-dir DIR  Directory to install the built binary (default: ~/.local/bin)
  --config FILE      Path to the kubelingo config file (default: ~/.config/kubelingo/config.toml)
EOF
}

# Defaults
REPO_DIR=$(pwd)
INSTALL_DIR="$HOME/.local/bin"
CONFIG_FILE="$HOME/.config/kubelingo/config.toml"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --repo-dir) REPO_DIR="$(realpath "$2")"; shift 2;;
    --install-dir) INSTALL_DIR="$(realpath "$2")"; shift 2;;
    --config) CONFIG_FILE="$(realpath "$2")"; shift 2;;
    -h|--help) print_usage; exit 0;;
    *) echo "Unknown option: $1"; print_usage; exit 1;;
  esac
done

# Check for cargo
if ! command -v cargo >/dev/null; then
  echo "Error: cargo not found. Install Rust toolchain first."
  exit 1
fi

# Build the Rust extension
echo "Building kubelingo-rs in $REPO_DIR..."
pushd "$REPO_DIR" >/dev/null
cargo build --release -p kubelingo-rs
popd >/dev/null

# Install the binary
mkdir -p "$INSTALL_DIR"
echo "Copying binary to $INSTALL_DIR..."
cp "$REPO_DIR/target/release/kubelingo-rs" "$INSTALL_DIR/"

# Update configuration
CONFIG_DIR=$(dirname "$CONFIG_FILE")
mkdir -p "$CONFIG_DIR"
echo "Updating config file at $CONFIG_FILE..."
if [[ -f "$CONFIG_FILE" ]]; then
  cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
fi

cat > "$CONFIG_FILE" <<EOF
[command_checker]
rust_extension_path = "$(realpath "$INSTALL_DIR/kubelingo-rs")"
enabled = true
EOF

echo "Done! Make sure $INSTALL_DIR is in your PATH and restart the Kubelingo CLI."