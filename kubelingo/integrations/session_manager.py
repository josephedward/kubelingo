#!/usr/bin/env python3
"""
session_manager.py: CKAD study session management with GoSandboxIntegration
"""
import subprocess
import os
import time
from pathlib import Path
from typing import Optional

from .gosandbox_integration import GoSandboxIntegration
from kubelingo.cli import Fore, Style

class CKADStudySession:
    def __init__(self, gosandbox_path: str = "../gosandbox"):
        self.gosandbox = GoSandboxIntegration(gosandbox_path)
        # Indicates whether session is initialized (cloud or local)
        self.session_active = False
        # If sandbox credentials acquisition fails, run in local-only mode
        self.cluster_enabled = True
        # Name of EKS cluster (if used)
        self.cluster_name = "ckad-practice"
        
    def initialize_session(self) -> bool:
        """Initialize a complete CKAD study session"""
        print("🚀 Initializing CKAD Study Session...")
        
        # Step 1: Acquire AWS credentials (sandbox)
        creds = self.gosandbox.acquire_credentials()
        if not creds:
            # Sandbox not available: offer local-only mode
            choice = input(
                "⚠️  Could not acquire AWS credentials (sandbox). Continue in local-only mode? (y/N): "
            ).strip().lower().startswith('y')
            if choice:
                print("ℹ️  Continuing in local-only mode (no cluster context)")
                self.cluster_enabled = False
                self.session_active = True
                return True
            print("❌ Aborting session initialization.")
            return False
            
        # Step 2: Export credentials to environment (if sandbox enabled)
        if self.cluster_enabled and not self.gosandbox.export_to_environment():
            print("❌ Failed to export AWS credentials to environment")
            return False
            
        # Step 3: Setup EKS cluster (optional, if sandbox enabled)
        if self.cluster_enabled:
            setup_cluster = input("🤔 Create EKS cluster for practice? (y/N): ").strip().lower().startswith('y')
            if setup_cluster and not self._setup_eks_cluster():
                print("⚠️  EKS setup failed, continuing with sandbox credentials only")
            
        # Mark session active (cloud or local)
        self.session_active = True
        print("✅ CKAD Study Session initialized successfully! ")
        return True
    
    def _setup_eks_cluster(self) -> bool:
        """Setup EKS cluster for practice.
        Note: Role ARN and VPC config are currently hard-coded and should be configured via SessionConfig or environment."""
        print(f"🔄 Creating EKS cluster: {self.cluster_name}")
        
        try:
            # Create EKS cluster (simplified)
            result = subprocess.run([
                "aws", "eks", "create-cluster",
                "--name", self.cluster_name,
                "--version", "1.24",
                "--role-arn", "arn:aws:iam::123456789012:role/eks-service-role",  # This would need to be dynamic
                "--resources-vpc-config", "subnetIds=subnet-12345,subnet-67890"  # This would need to be dynamic
            ], capture_output=True, text=True, timeout=1800)  # 30 minute timeout
            
            if result.returncode == 0:
                print("✅ EKS cluster created successfully")
                # Update kubeconfig
                return self.gosandbox.create_kubeconfig_for_eks(self.cluster_name)
            else:
                print(f"❌ EKS cluster creation failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ EKS cluster creation timed out")
            return False
        except Exception as e:
            print(f"❌ Error creating EKS cluster: {e}")
            return False
    
    def start_kubelingo(self):
        """Start the kubelingo vim editor with session context"""
        if not self.session_active:
            print("❌ Session not initialized. Run initialize_session() first.")
            return
            
        print("🎯 Starting Kubelingo Vim YAML Editor...")
        
        # Import and run the vim editor
        from modules.vim_yaml_editor import VimYamlEditor, vim_commands_quiz
        
        editor = VimYamlEditor()
        
        print(Fore.CYAN + "\n=== CKAD Study Session with Cloud Context ===" + Style.RESET_ALL)
        print(Fore.YELLOW + "1. Pod Exercise (with real cluster)" + Style.RESET_ALL)
        print(Fore.YELLOW + "2. ConfigMap Exercise" + Style.RESET_ALL)
        print(Fore.YELLOW + "3. Deployment Exercise" + Style.RESET_ALL)
        print(Fore.YELLOW + "4. Service Exercise" + Style.RESET_ALL)
        print(Fore.YELLOW + "5. Vim Commands Quiz" + Style.RESET_ALL)
        print(Fore.YELLOW + "6. Exit Session" + Style.RESET_ALL)
        
        while True:
            choice = input("\\nSelect option (1-6): ")
            
            if choice == "1":
                editor.run_interactive_exercise("pod", "name: nginx-app image: nginx:1.20")
                self._apply_to_cluster_prompt(editor, "pod")
            elif choice == "2":
                editor.run_interactive_exercise("configmap", "name: app-settings")
                self._apply_to_cluster_prompt(editor, "configmap")
            elif choice == "3":
                editor.run_interactive_exercise("deployment", "name: web-app replicas: 3")
                self._apply_to_cluster_prompt(editor, "deployment")
            elif choice == "4":
                editor.run_interactive_exercise("service", "name: web-service port: 80")
                self._apply_to_cluster_prompt(editor, "service")
            elif choice == "5":
                vim_commands_quiz()
            elif choice == "6":
                self.cleanup_session()
                break
            else:
                print("Invalid choice. Please select 1-6.")
    
    def _apply_to_cluster_prompt(self, editor, resource_type):
        """Prompt to apply the created resource to the cluster"""
        # If no cluster context, skip applying to cluster
        if not getattr(self, 'cluster_enabled', True):
            print("⚠️  No cluster configured. Skipping apply to cluster.")
            return
        apply = input(f"🤔 Apply {resource_type} to cluster? (y/N): ").strip().lower().startswith('y')
        if apply:
            # Find the most recent exercise file
            temp_files = list(editor.temp_dir.glob(f"{resource_type}-exercise.yaml"))
            if temp_files:
                latest_file = max(temp_files, key=lambda f: f.stat().st_mtime)
                self._apply_yaml_to_cluster(latest_file)
    
    def _apply_yaml_to_cluster(self, yaml_file: Path):
        """Apply YAML file to the cluster"""
        try:
            result = subprocess.run([
                "kubectl", "apply", "-f", str(yaml_file)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Applied to cluster: {result.stdout}")
                
                # Show the created resource
                resource_info = subprocess.run([
                    "kubectl", "get", "all", "-o", "wide"
                ], capture_output=True, text=True)
                
                if resource_info.returncode == 0:
                    print("\\n📋 Current cluster resources:")
                    print(resource_info.stdout)
            else:
                print(f"❌ Failed to apply: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error applying to cluster: {e}")
    
    def cleanup_session(self):
        """Cleanup the study session"""
        print("🧹 Cleaning up CKAD study session...")
        
        # Clean up any created resources
        cleanup = input("🤔 Delete all created resources from cluster? (y/N): ").lower().startswith('y')
        if cleanup:
            try:
                subprocess.run(["kubectl", "delete", "all", "--all"], check=True)
                print("✅ Cluster resources cleaned up")
            except Exception as e:
                print(f"⚠️  Error cleaning up resources: {e}")
        
        # Optionally delete EKS cluster (if cloud session)
        if getattr(self, 'cluster_enabled', True):
            delete_cluster = input(f"🤔 Delete EKS cluster '{self.cluster_name}'? (y/N): ").strip().lower().startswith('y')
            if delete_cluster:
                try:
                    subprocess.run([
                        "aws", "eks", "delete-cluster", "--name", self.cluster_name
                    ], check=True)
                    print(f"✅ EKS cluster '{self.cluster_name}' deletion initiated")
                except Exception as e:
                    print(f"⚠️  Error deleting cluster: {e}")
        
        self.session_active = False
        print("✅ Session cleanup complete")

if __name__ == "__main__":
    session = CKADStudySession()
    session.initialize_session()
    session.start_kubelingo()
