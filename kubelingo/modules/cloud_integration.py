import json
import subprocess
import os
from typing import Dict, List, Optional

class CloudEnvironmentManager:
    def __init__(self, cloud_provider: str = "aws"):
        self.cloud_provider = cloud_provider
        self.cluster_context = None
        
    def detect_cloud_environment(self) -> Dict[str, str]:
        """Detect current cloud environment and cluster context"""
        try:
            # Check if we're in an EKS environment
            result = subprocess.run(
                ["kubectl", "config", "current-context"],
                capture_output=True, text=True
            )
            
            if "eks" in result.stdout.lower():
                return {
                    "provider": "aws",
                    "cluster_type": "eks",
                    "context": result.stdout.strip()
                }
            
            # Check for other cloud providers
            if "gke" in result.stdout.lower():
                return {"provider": "gcp", "cluster_type": "gke"}
            
            if "aks" in result.stdout.lower():
                return {"provider": "azure", "cluster_type": "aks"}
                
            return {"provider": "local", "cluster_type": "unknown"}
            
        except subprocess.CalledProcessError:
            return {"provider": "unknown", "cluster_type": "unknown"}
    
    def load_cloud_specific_exercises(self) -> List[Dict]:
        """Load exercises specific to detected cloud environment"""
        cloud_info = self.detect_cloud_environment()
        
        if cloud_info["provider"] == "aws":
            return self._load_aws_exercises()
        elif cloud_info["provider"] == "gcp":
            return self._load_gcp_exercises()
        else:
            return []
    
    def _load_aws_exercises(self) -> List[Dict]:
        """Load AWS-specific CKAD exercises"""
        aws_exercises = [
            {
                "category": "AWS Storage",
                "question_type": "yaml_edit",
                "prompt": "Create a Pod that mounts an EBS volume using PVC",
                "starting_yaml": """apiVersion: v1
kind: Pod
metadata:
  name: ebs-pod
  namespace: ckad-practice
spec:
  containers:
  - name: app
    image: nginx:1.21
    volumeMounts:
    - name: ebs-storage
      mountPath: /data
  volumes:
  - name: ebs-storage
    persistentVolumeClaim:
      claimName: # TODO: Add PVC name
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: # TODO: Add PVC name
  namespace: ckad-practice
spec:
  accessModes:
    - # TODO: Set access mode
  resources:
    requests:
      storage: # TODO: Set storage size
  storageClassName: # TODO: Set AWS storage class""",
                "correct_yaml": """apiVersion: v1
kind: Pod
metadata:
  name: ebs-pod
  namespace: ckad-practice
spec:
  containers:
  - name: app
    image: nginx:1.21
    volumeMounts:
    - name: ebs-storage
      mountPath: /data
  volumes:
  - name: ebs-storage
    persistentVolumeClaim:
      claimName: ebs-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ebs-pvc
  namespace: ckad-practice
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: gp2""",
                "explanation": "EBS-backed storage using AWS gp2 storage class with proper PVC configuration"
            },
            {
                "category": "AWS Networking",
                "question_type": "yaml_edit", 
                "prompt": "Create a Service that exposes an application via AWS Load Balancer",
                "starting_yaml": """apiVersion: v1
kind: Service
metadata:
  name: web-service
  namespace: ckad-practice
  annotations:
    # TODO: Add AWS Load Balancer annotations
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
  type: # TODO: Set service type""",
                "correct_yaml": """apiVersion: v1
kind: Service
metadata:
  name: web-service
  namespace: ckad-practice
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
  type: LoadBalancer""",
                "explanation": "AWS Network Load Balancer service with proper annotations for internet-facing exposure"
            }
        ]
        
        return aws_exercises
    
    def validate_cloud_resources(self, yaml_content: str) -> Dict[str, bool]:
        """Validate that cloud-specific resources can be created"""
        try:
            # Apply YAML to cluster in dry-run mode
            result = subprocess.run([
                "kubectl", "apply", "--dry-run=server", "-f", "-"
            ], input=yaml_content, text=True, capture_output=True)
            
            return {
                "valid": result.returncode == 0,
                "message": result.stderr if result.returncode != 0 else "Valid",
                "cloud_specific": True
            }
            
        except Exception as e:
            return {
                "valid": False,
                "message": f"Validation error: {str(e)}",
                "cloud_specific": True
            }