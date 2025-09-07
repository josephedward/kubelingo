#!/bin/bash
set -e

echo "Installing Krew plugin manager for kubectl..."

# Install Krew
(
  set -x
  cd "$(mktemp -d)" &&
  OS="$(uname | tr '[:upper:]' '[:lower:]')" &&
  ARCH="$(uname -m | sed -e 's/x86_64/amd64/' -e 's/\(arm\)\(64\)\?.*/\1\2/' -e 's/aarch64/arm64/')" &&
  KREW="krew-${OS}_${ARCH}" &&
  curl -fsSLO "https://github.com/kubernetes-sigs/krew/releases/latest/download/${KREW}.tar.gz" &&
  tar zxvf "${KREW}.tar.gz" &&
  ./"${KREW}" install krew
)

echo -e "\nKrew installed! Add to your PATH with:"
echo 'export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"'
echo -e "\nAdd this to your shell profile file (~/.zshrc, ~/.bashrc, etc.) and restart your terminal."

echo -e "\nInstalling kubectl-validate plugin..."
kubectl krew install validate

echo -e "\nInstallation complete! Verify with:"
echo "kubectl validate --help"
