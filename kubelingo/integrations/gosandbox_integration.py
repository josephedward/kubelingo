#!/usr/bin/env python3
"""
gosandbox_integration.py: Integration with gosandbox Go application
"""
import os
import subprocess
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
try:
    import yaml
except ImportError:
    yaml = None

@dataclass
class AWSCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str
    region: str = "us-east-1"
    
    def to_env_vars(self) -> Dict[str, str]:
        return {
            "AWS_ACCESS_KEY_ID": self.access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
            "AWS_SESSION_TOKEN": self.session_token,
            "AWS_DEFAULT_REGION": self.region
        }

class GoSandboxIntegration:
    def __init__(self, gosandbox_path: str = "../gosandbox"):
        self.gosandbox_path = Path(gosandbox_path)
        self.credentials: Optional[AWSCredentials] = None
        
    def check_gosandbox_available(self) -> bool:
        """Check if gosandbox is available and configured"""
        if not self.gosandbox_path.exists():
            print(f"❌ gosandbox not found at {self.gosandbox_path}")
            return False
            
        env_file = self.gosandbox_path / ".env"
        if not env_file.exists():
            print(f"❌ .env file not found at {env_file}")
            return False
            
        return True
    
    def acquire_credentials(self) -> Optional[AWSCredentials]:
        """Acquire AWS credentials via gosandbox"""
        if not self.check_gosandbox_available():
            return None
            
        print("🔄 Acquiring AWS credentials via gosandbox...")
        
        try:
            # Change to gosandbox directory and run
            result = subprocess.run(
                ["go", "run", "main.go", "prod"],
                cwd=self.gosandbox_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                print(f"❌ gosandbox failed: {result.stderr}")
                return None
                
            # Parse credentials from output or files
            creds = self._parse_credentials_output(result.stdout)
            if creds:
                self.credentials = creds
                print("✅ AWS credentials acquired successfully")
                return creds
                
        except subprocess.TimeoutExpired:
            print("❌ gosandbox timed out")
        except Exception as e:
            print(f"❌ Error running gosandbox: {e}")
            
        return None
    
    def _parse_credentials_output(self, output: str) -> Optional[AWSCredentials]:
        """Parse AWS credentials from gosandbox output"""
        # Look for credentials in the output
        lines = output.split('\n')
        creds_data = {}
        
        for line in lines:
            if "AWS_ACCESS_KEY_ID" in line:
                creds_data["access_key_id"] = line.split("=")[1].strip()
            elif "AWS_SECRET_ACCESS_KEY" in line:
                creds_data["secret_access_key"] = line.split("=")[1].strip()
            elif "AWS_SESSION_TOKEN" in line:
                creds_data["session_token"] = line.split("=")[1].strip()
                
        if len(creds_data) == 3:
            return AWSCredentials(**creds_data)
            
        # Fallback: check for credentials file
        creds_file = self.gosandbox_path / "test" / "credentials.txt"
        if creds_file.exists():
            return self._parse_credentials_file(creds_file)
            
        return None
    
    def _parse_credentials_file(self, file_path: Path) -> Optional[AWSCredentials]:
        """Parse credentials from file"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Parse AWS credentials format
            creds_data = {}
            for line in content.split('\n'):
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == "AWS_ACCESS_KEY_ID":
                        creds_data["access_key_id"] = value
                    elif key == "AWS_SECRET_ACCESS_KEY":
                        creds_data["secret_access_key"] = value
                    elif key == "AWS_SESSION_TOKEN":
                        creds_data["session_token"] = value
                        
            if len(creds_data) == 3:
                return AWSCredentials(**creds_data)
                
        except Exception as e:
            print(f"❌ Error parsing credentials file: {e}")
            
        return None
    
    def export_to_environment(self) -> bool:
        """Export credentials to current environment"""
        if not self.credentials:
            print("❌ No credentials available")
            return False
            
        env_vars = self.credentials.to_env_vars()
        for key, value in env_vars.items():
            os.environ[key] = value
            
        print("✅ AWS credentials exported to environment")
        return True
    
    def create_kubeconfig_for_eks(self, cluster_name: str = "ckad-practice") -> bool:
        """Create kubeconfig for EKS cluster"""
        if not self.credentials:
            print("❌ No AWS credentials available")
            return False
            
        try:
            # Export credentials first
            self.export_to_environment()
            
            # Update kubeconfig for EKS
            result = subprocess.run([
                "aws", "eks", "update-kubeconfig",
                "--region", self.credentials.region,
                "--name", cluster_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Kubeconfig updated for EKS cluster: {cluster_name}")
                return True
            else:
                print(f"❌ Failed to update kubeconfig: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating kubeconfig: {e}")
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GoSandbox Integration")
    parser.add_argument("--acquire", action="store_true", help="Acquire AWS credentials")
    parser.add_argument("--export", action="store_true", help="Export credentials to environment")
    parser.add_argument("--kubeconfig", help="Update kubeconfig for EKS cluster")
    parser.add_argument("--gosandbox-path", default="../gosandbox", help="Path to gosandbox directory")
    
    args = parser.parse_args()
    
    integration = GoSandboxIntegration(args.gosandbox_path)
    
    if args.acquire:
        integration.acquire_credentials()
    
    if args.export:
        integration.export_to_environment()
        
    if args.kubeconfig:
        integration.create_kubeconfig_for_eks(args.kubeconfig)
