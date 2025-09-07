#!/usr/bin/env python3
"""
Installation Setup Script for Kubernetes AI Tools

This script helps install and configure all the AI-powered Kubernetes tools
mentioned in the system design.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def run_command(cmd, description="", check=True):
    """Run a shell command with error handling"""
    print(f"Running: {description or cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        if result.stdout:
            print(f"Output: {result.stdout}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return False

def check_command_exists(cmd):
    """Check if a command exists in PATH"""
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_python_deps():
    """Install Python dependencies"""
    print("=== Installing Python Dependencies ===")
    return run_command("pip install -r requirements.txt", "Installing Python packages")

def install_kubectl_ai_google():
    """Install Google's kubectl-ai"""
    print("\n=== Installing kubectl-ai (Google Cloud) ===")
    
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        # Try homebrew first
        if check_command_exists(["brew", "--version"]):
            return run_command("brew tap sozercan/kubectl-ai https://github.com/sozercan/kubectl-ai && brew install kubectl-ai", 
                             "Installing kubectl-ai via Homebrew")
    
    # Fallback: manual installation
    print("Installing kubectl-ai manually...")
    install_script = "curl -sSL https://raw.githubusercontent.com/GoogleCloudPlatform/kubectl-ai/main/install.sh | bash"
    return run_command(install_script, "Installing kubectl-ai manually")

def install_kubectl_ai_sozercan():
    """Install sozercan's kubectl-ai"""
    print("\n=== Installing kubectl-ai (sozercan) ===")
    
    # Try krew first (if kubectl is available)
    if check_command_exists(["kubectl", "version", "--client"]):
        if check_command_exists(["kubectl", "krew"]):
            if run_command("kubectl krew index add kubectl-ai https://github.com/sozercan/kubectl-ai", check=False):
                return run_command("kubectl krew install kubectl-ai/kubectl-ai", "Installing via krew")
    
    # Fallback: direct download
    system = platform.system().lower()
    if system == "darwin":
        arch = "arm64" if platform.machine() == "arm64" else "amd64"
        download_url = f"https://github.com/sozercan/kubectl-ai/releases/latest/download/kubectl-ai_Darwin_{arch}.tar.gz"
        
        commands = [
            f"curl -L {download_url} -o kubectl-ai.tar.gz",
            "tar -zxvf kubectl-ai.tar.gz",
            "chmod +x kubectl-ai", 
            "sudo mv kubectl-ai /usr/local/bin/",
            "rm kubectl-ai.tar.gz"
        ]
        
        for cmd in commands:
            if not run_command(cmd):
                return False
        return True
    
    return False

def install_kube_copilot():
    """Install Kube-Copilot"""
    print("\n=== Installing Kube-Copilot ===")
    
    # Try Go install first
    if check_command_exists(["go", "version"]):
        if run_command("go install github.com/feiskyer/kube-copilot/cmd/kube-copilot@latest", 
                      "Installing via go install"):
            # Copy to local bin if GOPATH is set
            gopath = os.environ.get("GOPATH", os.path.expanduser("~/go"))
            src = f"{gopath}/bin/kube-copilot"
            if os.path.exists(src):
                return run_command(f"cp {src} ./bin/", "Copying to local bin", check=False)
            return True
    
    # Fallback: pip install if available
    return run_command("pip install kube-copilot", "Installing via pip", check=False)

def install_k8sgpt():
    """Install K8sGPT"""
    print("\n=== Installing K8sGPT ===")
    
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        if check_command_exists(["brew", "--version"]):
            return run_command("brew tap k8sgpt-ai/tap && brew install k8sgpt", 
                             "Installing K8sGPT via Homebrew")
    
    # Try pip
    if run_command("pip install k8sgpt", "Installing K8sGPT via pip", check=False):
        return True
    
    # Manual download
    arch = "arm64" if platform.machine() == "arm64" else "amd64"
    if system == "darwin":
        download_url = f"https://github.com/k8sgpt-ai/k8sgpt/releases/latest/download/k8sgpt_Darwin_{arch}.tar.gz"
    elif system == "linux":
        download_url = f"https://github.com/k8sgpt-ai/k8sgpt/releases/latest/download/k8sgpt_Linux_{arch}.tar.gz"
    else:
        print("Unsupported platform for manual K8sGPT install")
        return False
    
    commands = [
        f"curl -L {download_url} -o k8sgpt.tar.gz",
        "tar -zxvf k8sgpt.tar.gz",
        "chmod +x k8sgpt",
        "mv k8sgpt ./bin/",
        "rm k8sgpt.tar.gz"
    ]
    
    for cmd in commands:
        if not run_command(cmd):
            return False
    return True

def install_kopylot():
    """Install KoPylot"""
    print("\n=== Installing KoPylot ===")
    return run_command("pip install kopylot", "Installing KoPylot via pip")

def install_static_tools():
    """Install static validation tools"""
    print("\n=== Installing Static Validation Tools ===")
    
    tools = {
        "kubeconform": "go install github.com/yannh/kubeconform/cmd/kubeconform@latest",
        "kube-score": "brew install kube-score" if platform.system() == "Darwin" else None,
        "kube-linter": "go install golang.stackrox.io/kube-linter/cmd/kube-linter@latest",
        "checkov": "pip install checkov",
        "trivy": "brew install aquasecurity/trivy/trivy" if platform.system() == "Darwin" else None
    }
    
    results = {}
    for tool, install_cmd in tools.items():
        if install_cmd:
            print(f"\nInstalling {tool}...")
            results[tool] = run_command(install_cmd, f"Installing {tool}", check=False)
        else:
            print(f"No install command for {tool} on this platform")
            results[tool] = False
    
    return results

def setup_environment():
    """Setup project environment"""
    print("\n=== Setting Up Environment ===")
    
    # Create bin directory
    bin_dir = Path("./bin")
    bin_dir.mkdir(exist_ok=True)
    print("Created ./bin directory")
    
    # Create .env template
    env_template = """# AI API Keys
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
XAI_API_KEY=your_xai_key_here

# CLI Tool Configurations
KOPYLOT_AUTH_TOKEN=your_openai_key_here

# Ollama Configuration (for local LLMs)
OLLAMA_HOST=http://localhost:11434

# Optional: Custom API endpoints
OPENAI_API_BASE=https://api.openai.com/v1
"""
    
    env_file = Path(".env")
    if not env_file.exists():
        with open(env_file, "w") as f:
            f.write(env_template)
        print("Created .env template file")
        print("Please edit .env and add your API keys!")
    else:
        print(".env file already exists")
    
    # Add bin to PATH instruction
    bin_path = bin_dir.absolute()
    print(f"\nTo use locally installed tools, add to your PATH:")
    print(f"export PATH=\"{bin_path}:$PATH\"")
    
    return True

def verify_installation():
    """Verify installations"""
    print("\n=== Verifying Installations ===")
    
    tools_to_check = [
        ("kubectl-ai", ["kubectl-ai", "--help"]),
        ("kubectl", ["kubectl", "ai", "--help"]),
        ("kube-copilot", ["kube-copilot", "--help"]),
        ("k8sgpt", ["k8sgpt", "version"]),
        ("kopylot", ["kopylot", "--help"]),
        ("kubeconform", ["kubeconform", "-h"]),
        ("kube-score", ["kube-score", "--help"]),
        ("kube-linter", ["kube-linter", "version"]),
        ("checkov", ["checkov", "--version"]),
        ("trivy", ["trivy", "--version"])
    ]
    
    results = {}
    for tool_name, cmd in tools_to_check:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            success = result.returncode == 0
            results[tool_name] = success
            status = "✓" if success else "✗"
            print(f"{tool_name}: {status}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            results[tool_name] = False
            print(f"{tool_name}: ✗ (not found or timeout)")
    
    return results

def main():
    """Main installation routine"""
    print("Kubernetes AI Tools Installation Script")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--verify-only":
        verify_installation()
        return
    
    # Setup environment first
    setup_environment()
    
    # Install Python dependencies
    if not install_python_deps():
        print("Failed to install Python dependencies")
        return
    
    # Install AI CLI tools
    tools_results = {
        "kubectl-ai-google": install_kubectl_ai_google(),
        "kubectl-ai-sozercan": install_kubectl_ai_sozercan(), 
        "kube-copilot": install_kube_copilot(),
        "k8sgpt": install_k8sgpt(),
        "kopylot": install_kopylot()
    }
    
    # Install static validation tools
    static_results = install_static_tools()
    tools_results.update(static_results)
    
    # Summary
    print("\n=== Installation Summary ===")
    for tool, success in tools_results.items():
        status = "✓ Installed" if success else "✗ Failed"
        print(f"{tool}: {status}")
    
    # Verification
    print("\n=== Running Verification ===")
    verify_results = verify_installation()
    
    successful_installs = sum(1 for success in tools_results.values() if success)
    total_tools = len(tools_results)
    
    print(f"\nInstallation completed: {successful_installs}/{total_tools} tools installed successfully")
    
    if successful_installs > 0:
        print("\nNext steps:")
        print("1. Edit the .env file and add your API keys")
        print("2. Add ./bin to your PATH if you installed tools locally")
        print("3. Test the system with: python k8s_manifest_generator.py --mode question --question-count 1")
        print("4. Try generating manifests with: python k8s_manifest_generator.py --prompt 'create nginx deployment'")

if __name__ == "__main__":
    main()