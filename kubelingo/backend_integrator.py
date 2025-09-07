#!/usr/bin/env python3
"""
Backend Integrator Module

This module manages integration with various CLI tools for Kubernetes manifest generation
and validation, including kubectl-ai variants, K8sGPT, KoPylot, and Kube-Copilot.
"""

import os
import subprocess
import json
import tempfile
import shlex
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import pexpect

class BackendType(Enum):
    KUBECTL_AI_GOOGLE = "kubectl-ai-google"
    KUBECTL_AI_SOZERCAN = "kubectl-ai-sozercan" 
    KUBE_COPILOT = "kube-copilot"
    K8SGPT = "k8sgpt"
    KOPYLOT = "kopylot"

@dataclass
class BackendResult:
    backend: str
    success: bool
    output: str
    error: str
    yaml_content: Optional[str] = None
    execution_time: Optional[float] = None

class BackendIntegrator:
    def __init__(self, env_file_path: str = ".env"):
        self.env_vars = self._load_env_vars(env_file_path)
        self.backend_configs = self._init_backend_configs()
        
    def _load_env_vars(self, env_file_path: str) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value.strip('"').strip("'")
        
        # Also include existing environment variables
        env_vars.update(dict(os.environ))
        return env_vars
    
    def _init_backend_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize configuration for each backend"""
        return {
            BackendType.KUBECTL_AI_GOOGLE.value: {
                "command": "kubectl-ai",
                "env_keys": ["GEMINI_API_KEY", "OPENAI_API_KEY"],
                "install_check": "kubectl-ai --help",
                "description": "Google Cloud kubectl-ai plugin"
            },
            BackendType.KUBECTL_AI_SOZERCAN.value: {
                "command": "kubectl",
                "subcommand": "ai", 
                "env_keys": ["OPENAI_API_KEY"],
                "install_check": "kubectl ai --help",
                "description": "sozercan kubectl-ai plugin"
            },
            BackendType.KUBE_COPILOT.value: {
                "command": "kube-copilot",
                "env_keys": ["OPENAI_API_KEY", "GEMINI_API_KEY"],
                "install_check": "kube-copilot --help",
                "description": "Kube-Copilot AI assistant"
            },
            BackendType.K8SGPT.value: {
                "command": "k8sgpt",
                "env_keys": ["OPENAI_API_KEY", "GEMINI_API_KEY"],
                "install_check": "k8sgpt version",
                "description": "K8sGPT cluster analysis tool"
            },
            BackendType.KOPYLOT.value: {
                "command": "kopylot",
                "env_keys": ["KOPYLOT_AUTH_TOKEN", "OPENAI_API_KEY"],
                "install_check": "kopylot --help",
                "description": "KoPylot Kubernetes assistant"
            }
        }
    
    def check_backend_availability(self, backend: str) -> Tuple[bool, str]:
        """Check if a backend is available and properly configured"""
        if backend not in self.backend_configs:
            return False, f"Unknown backend: {backend}"
            
        config = self.backend_configs[backend]
        
        # Check if command is installed
        try:
            subprocess.run(
                shlex.split(config["install_check"]), 
                capture_output=True, 
                check=False,
                timeout=10
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, f"Command '{config['command']}' not found or not responding"
        
        # Check environment variables
        missing_vars = []
        for env_key in config["env_keys"]:
            if env_key not in self.env_vars or not self.env_vars[env_key]:
                missing_vars.append(env_key)
                
        if missing_vars:
            return False, f"Missing environment variables: {', '.join(missing_vars)}"
            
        return True, "Backend available"
    
    def generate_with_kubectl_ai_google(self, prompt: str) -> BackendResult:
        """Generate manifest using Google's kubectl-ai"""
        try:
            env = dict(self.env_vars)
            cmd = ["kubectl-ai", "--quiet", prompt]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            
            output = result.stdout.strip()
            yaml_content = self._extract_yaml_from_output(output)
            
            return BackendResult(
                backend=BackendType.KUBECTL_AI_GOOGLE.value,
                success=result.returncode == 0,
                output=output,
                error=result.stderr,
                yaml_content=yaml_content
            )
            
        except Exception as e:
            return BackendResult(
                backend=BackendType.KUBECTL_AI_GOOGLE.value,
                success=False,
                output="",
                error=str(e)
            )
    
    def generate_with_kubectl_ai_sozercan(self, prompt: str) -> BackendResult:
        """Generate manifest using sozercan's kubectl-ai"""
        try:
            env = dict(self.env_vars)
            cmd = ["kubectl", "ai", prompt]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            
            output = result.stdout.strip()
            yaml_content = self._extract_yaml_from_output(output)
            
            return BackendResult(
                backend=BackendType.KUBECTL_AI_SOZERCAN.value,
                success=result.returncode == 0,
                output=output,
                error=result.stderr,
                yaml_content=yaml_content
            )
            
        except Exception as e:
            return BackendResult(
                backend=BackendType.KUBECTL_AI_SOZERCAN.value,
                success=False,
                output="",
                error=str(e)
            )
    
    def generate_with_kube_copilot(self, prompt: str) -> BackendResult:
        """Generate manifest using Kube-Copilot"""
        try:
            env = dict(self.env_vars)
            cmd = ["kube-copilot", "generate", "--prompt", prompt]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            
            output = result.stdout.strip()
            yaml_content = self._extract_yaml_from_output(output)
            
            return BackendResult(
                backend=BackendType.KUBE_COPILOT.value,
                success=result.returncode == 0,
                output=output,
                error=result.stderr,
                yaml_content=yaml_content
            )
            
        except Exception as e:
            return BackendResult(
                backend=BackendType.KUBE_COPILOT.value,
                success=False,
                output="",
                error=str(e)
            )
    
    def generate_with_k8sgpt(self, prompt: str, base_yaml: Optional[str] = None) -> BackendResult:
        """Generate/analyze manifest using K8sGPT"""
        try:
            env = dict(self.env_vars)
            
            # K8sGPT is primarily for analysis, but we can use it for generation
            # by providing a base manifest and asking it to modify/improve
            if base_yaml is None:
                base_yaml = self._create_minimal_base_yaml(prompt)
            
            # Write base YAML to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(base_yaml)
                temp_file = f.name
            
            try:
                # Use k8sgpt to analyze and suggest improvements
                cmd = ["k8sgpt", "generate", "--prompt", f"Improve this YAML for: {prompt}", "--file", temp_file]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30
                )
                
                if result.returncode != 0:
                    # Fallback to analyze if generate doesn't work
                    cmd = ["k8sgpt", "analyze", "--explain", "--output", "json"]
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
                
                output = result.stdout.strip()
                yaml_content = self._extract_yaml_from_output(output) or base_yaml
                
                return BackendResult(
                    backend=BackendType.K8SGPT.value,
                    success=result.returncode == 0,
                    output=output,
                    error=result.stderr,
                    yaml_content=yaml_content
                )
                
            finally:
                os.unlink(temp_file)
                
        except Exception as e:
            return BackendResult(
                backend=BackendType.K8SGPT.value,
                success=False,
                output="",
                error=str(e)
            )
    
    def generate_with_kopylot(self, prompt: str) -> BackendResult:
        """Generate manifest using KoPylot"""
        try:
            env = dict(self.env_vars)
            
            # KoPylot has an interactive chat interface
            # We'll try to use it non-interactively with pexpect
            child = pexpect.spawn('kopylot chat', env=env, timeout=30)
            
            # Send the prompt
            child.sendline(f"Generate Kubernetes YAML: {prompt}")
            
            # Wait for response
            child.expect(pexpect.EOF, timeout=30)
            output = child.before.decode('utf-8')
            
            yaml_content = self._extract_yaml_from_output(output)
            
            return BackendResult(
                backend=BackendType.KOPYLOT.value,
                success=child.exitstatus == 0 if child.exitstatus is not None else True,
                output=output,
                error="",
                yaml_content=yaml_content
            )
            
        except Exception as e:
            # Fallback: try direct command if available
            try:
                env = dict(self.env_vars)
                # Some versions might support direct generation
                result = subprocess.run(
                    ["kopylot", "generate", prompt],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30
                )
                
                output = result.stdout.strip()
                yaml_content = self._extract_yaml_from_output(output)
                
                return BackendResult(
                    backend=BackendType.KOPYLOT.value,
                    success=result.returncode == 0,
                    output=output,
                    error=result.stderr,
                    yaml_content=yaml_content
                )
            except:
                return BackendResult(
                    backend=BackendType.KOPYLOT.value,
                    success=False,
                    output="",
                    error=str(e)
                )
    
    def _extract_yaml_from_output(self, output: str) -> Optional[str]:
        """Extract YAML content from command output"""
        lines = output.split('\n')
        yaml_lines = []
        in_yaml_block = False
        
        for line in lines:
            # Check for markdown yaml block
            if '```yaml' in line.lower():
                in_yaml_block = True
                continue
            elif '```' in line and in_yaml_block:
                break
            elif in_yaml_block:
                yaml_lines.append(line)
            # Check for lines that look like YAML (start with apiVersion, kind, etc.)
            elif line.strip().startswith(('apiVersion:', 'kind:', 'metadata:')):
                in_yaml_block = True
                yaml_lines.append(line)
        
        yaml_content = '\n'.join(yaml_lines).strip()
        return yaml_content if yaml_content else None
    
    def _create_minimal_base_yaml(self, prompt: str) -> str:
        """Create a minimal base YAML for K8sGPT to work with"""
        # Simple heuristic to determine resource type
        prompt_lower = prompt.lower()
        
        if 'deployment' in prompt_lower:
            return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: base-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: base
  template:
    metadata:
      labels:
        app: base
    spec:
      containers:
      - name: base
        image: nginx:latest
        ports:
        - containerPort: 80"""
        
        elif 'service' in prompt_lower:
            return """apiVersion: v1
kind: Service
metadata:
  name: base-service
spec:
  selector:
    app: base
  ports:
  - port: 80
    targetPort: 80"""
    
        else:
            # Default to Pod
            return """apiVersion: v1
kind: Pod
metadata:
  name: base-pod
spec:
  containers:
  - name: base
    image: nginx:latest
    ports:
    - containerPort: 80"""
    
    def run_backend(self, backend: str, prompt: str, **kwargs) -> BackendResult:
        """Run a specific backend with error handling"""
        available, message = self.check_backend_availability(backend)
        if not available:
            return BackendResult(
                backend=backend,
                success=False,
                output="",
                error=f"Backend not available: {message}"
            )
        
        generators = {
            BackendType.KUBECTL_AI_GOOGLE.value: self.generate_with_kubectl_ai_google,
            BackendType.KUBECTL_AI_SOZERCAN.value: self.generate_with_kubectl_ai_sozercan,
            BackendType.KUBE_COPILOT.value: self.generate_with_kube_copilot,
            BackendType.K8SGPT.value: self.generate_with_k8sgpt,
            BackendType.KOPYLOT.value: self.generate_with_kopylot
        }
        
        generator = generators.get(backend)
        if not generator:
            return BackendResult(
                backend=backend,
                success=False,
                output="",
                error=f"No generator found for backend: {backend}"
            )
        
        return generator(prompt, **kwargs)
    
    def run_multiple_backends(self, backends: List[str], prompt: str) -> List[BackendResult]:
        """Run multiple backends in parallel"""
        results = []
        for backend in backends:
            result = self.run_backend(backend, prompt)
            results.append(result)
        return results
    
    def get_available_backends(self) -> List[str]:
        """Get list of available backends"""
        available = []
        for backend in self.backend_configs.keys():
            is_available, _ = self.check_backend_availability(backend)
            if is_available:
                available.append(backend)
        return available

def main():
    """Demo usage of the backend integrator"""
    integrator = BackendIntegrator()
    
    # Check available backends
    print("=== Backend Availability Check ===")
    for backend in integrator.backend_configs.keys():
        available, message = integrator.check_backend_availability(backend)
        status = "✓ Available" if available else "✗ Not available"
        print(f"{backend}: {status} - {message}")
    
    print("\n=== Available Backends ===")
    available_backends = integrator.get_available_backends()
    print(f"Available backends: {available_backends}")
    
    # Test with available backends
    if available_backends:
        test_prompt = "Create a simple nginx pod with 2 replicas"
        print(f"\n=== Testing with prompt: '{test_prompt}' ===")
        
        for backend in available_backends[:2]:  # Test first 2 available
            print(f"\nTesting {backend}...")
            result = integrator.run_backend(backend, test_prompt)
            print(f"Success: {result.success}")
            if result.yaml_content:
                print("Generated YAML preview:")
                print(result.yaml_content[:200] + "..." if len(result.yaml_content) > 200 else result.yaml_content)
            if result.error:
                print(f"Error: {result.error}")

if __name__ == "__main__":
    main()