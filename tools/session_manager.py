"""
tools/session_manager.py: Manage CKAD study sessions with cloud resources.
"""
import logging
import sys
from datetime import datetime, timedelta

class SessionConfig:
    """
    Configuration for CKAD study sessions.
    """
    def __init__(
        self,
        session_duration: timedelta = timedelta(hours=4),
        cluster_config: dict = None,
        namespaces: list = None,
        monitoring_enabled: bool = True,
        auto_cleanup: bool = True
    ):
        self.session_duration = session_duration
        self.cluster_config = cluster_config or {}
        self.namespaces = namespaces or []
        self.monitoring_enabled = monitoring_enabled
        self.auto_cleanup = auto_cleanup

class CKADStudySession:
    """
    Main orchestrator for CKAD study sessions with cloud resources.
    """
    def __init__(self, session_id: str = None, config: SessionConfig = None):
        self.session_id = session_id or f"ckad-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        self.config = config or SessionConfig()
        self.start_time = None
        self.expires_at = None
        self.cluster_name = None
        self.cluster_status = None
        self.status = 'created'
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)

    def initialize_session(self) -> None:
        """
        Initializes a complete CKAD study environment.
        """
        self.logger.info(f"Initializing session {self.session_id}")
        # TODO: integrate AWS credential acquisition and EKS cluster creation
        self.start_time = datetime.utcnow()
        self.expires_at = self.start_time + self.config.session_duration
        self.cluster_name = self.session_id
        self.cluster_status = 'ACTIVE'
        self.status = 'active'
        self.logger.info("Session initialized successfully")

    def get_status(self) -> dict:
        """
        Returns current session status and metrics.
        """
        time_remaining = (self.expires_at - datetime.utcnow()) if self.expires_at else timedelta(0)
        return {
            "session_id": self.session_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() + "Z" if self.start_time else None,
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
            "time_remaining": str(time_remaining),
            "cluster_name": self.cluster_name,
            "cluster_status": self.cluster_status,
            "node_count": self.config.cluster_config.get("node_count", 0),
            "pod_count": 0,
            "aws_costs": 0.0,
            "exercises_completed": 0,
            "exercises_total": 0
        }

    def extend_session(self, minutes: int = 30) -> bool:
        """
        Attempts to extend the session duration.
        """
        if not self.expires_at:
            self.logger.warning("Cannot extend session before initialization")
            return False
        self.expires_at += timedelta(minutes=minutes)
        self.logger.info(f"Session extended by {minutes} minutes")
        return True

    def cleanup_session(self) -> None:
        """
        Cleans up all cloud resources and terminates the session.
        """
        self.logger.info("Cleaning up session resources")
        self.status = 'terminated'
        if self.config.auto_cleanup:
            self.logger.info("Auto cleanup enabled: cleaning up resources")
        else:
            self.logger.info("Auto cleanup disabled")

    def start_kubelingo(self, exercise_filter: str = None) -> None:
        """
        Launches kubelingo with optional exercise filter.
        """
        self.logger.info("Starting kubelingo quiz")
        try:
            from cli_quiz import main as cli_main
        except ImportError:
            self.logger.error("kubelingo CLI not found (cli_quiz)")
            return
        argv_backup = sys.argv.copy()
        sys.argv = [argv_backup[0]]
        if exercise_filter:
            sys.argv.extend(['-c', exercise_filter])
        try:
            cli_main()
        except SystemExit as e:
            self.logger.info(f"kubelingo CLI exited with code {e.code}")
        finally:
            sys.argv = argv_backup#!/usr/bin/env python3
"""
session_manager.py: CKAD study session management with gosandbox integration
"""
import os
import subprocess
import time
from pathlib import Path
from typing import Optional
from .gosandbox_integration import GoSandboxIntegration, AWSCredentials

class CKADStudySession:
    def __init__(self, gosandbox_path: str = "../gosandbox"):
        self.gosandbox = GoSandboxIntegration(gosandbox_path)
        self.session_active = False
        self.cluster_name = "ckad-practice"
        
    def initialize_session(self) -> bool:
        """Initialize a complete CKAD study session"""
        print("🚀 Initializing CKAD Study Session...")
        
        # Step 1: Acquire AWS credentials
        if not self.gosandbox.acquire_credentials():
            print("❌ Failed to acquire AWS credentials")
            return False
            
        # Step 2: Export to environment
        if not self.gosandbox.export_to_environment():
            print("❌ Failed to export credentials")
            return False
            
        # Step 3: Setup EKS cluster (optional)
        setup_cluster = input("🤔 Create EKS cluster for practice? (y/N): ").lower().startswith('y')
        if setup_cluster:
            if not self._setup_eks_cluster():
                print("⚠️  EKS setup failed, continuing with local practice")
            
        self.session_active = True
        print("✅ CKAD Study Session initialized successfully!")
        return True
    
    def _setup_eks_cluster(self) -> bool:
        """Setup EKS cluster for practice"""
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
        
        print("\\n=== CKAD Study Session with Cloud Context ===")
        print("1. Pod Exercise (with real cluster)")
        print("2. ConfigMap Exercise")
        print("3. Deployment Exercise") 
        print("4. Service Exercise")
        print("5. Vim Commands Quiz")
        print("6. Exit Session")
        
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
        apply = input(f"🤔 Apply {resource_type} to cluster? (y/N): ").lower().startswith('y')
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
        
        # Optionally delete EKS cluster
        if hasattr(self, 'cluster_name'):
            delete_cluster = input(f"🤔 Delete EKS cluster '{self.cluster_name}'? (y/N): ").lower().startswith('y')
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
