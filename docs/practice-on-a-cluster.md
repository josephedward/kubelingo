# Practice on a Real Kubernetes Cluster

This guide shows easy and low-cost ways to run Kubelingo against a real Kubernetes cluster. Kubelingo itself doesn’t talk to your cluster; you do, using `kubectl`. As long as your current `kubectl` context points to a cluster, your commands and YAML apply to that cluster while you practice.

## TL;DR Recommendations
- Fastest on macOS/Linux: `kind` (Kubernetes in Docker). Lightweight, disposable, free.
- Windows/macOS without fiddling: Rancher Desktop or Docker Desktop with Kubernetes enabled.
- Classic single-node option: `minikube` (works everywhere, many drivers).
- Linux-only, near-bare‑metal: `microk8s` (snap install, low overhead).
- Cloud (credits/real infra): GKE Autopilot, AKS, or EKS. Good realism; be mindful of costs and delete when done.

## Safe Workflow for Learning
1. Pick one cluster option below and create a cluster.
2. Confirm your context: `kubectl config current-context` and `kubectl get nodes`.
3. Create a scratch namespace:
   - `kubectl create namespace kubelingo-lab`
   - `kubectl config set-context --current --namespace=kubelingo-lab`
4. Run Kubelingo and answer questions with real `kubectl` commands or apply manifests.
5. Clean up:
   - Delete resources: `kubectl delete all --all` (only removes basic types) or delete the namespace: `kubectl delete ns kubelingo-lab`.
   - For local clusters, you can also delete the whole cluster when done.

Tip: Use `--dry-run=client -o yaml` to generate/validate manifests without changing the cluster, and `kubectl diff -f <file>` to preview changes.

## Local, Free Options

### 1) kind ( Kubernetes in Docker )
Best for quick, disposable clusters on macOS/Linux with Docker/Podman.

- Install: `brew install kind` (macOS), or see https://kind.sigs.k8s.io
- Create cluster:
  - `kind create cluster --name kubelingo`
  - Kubeconfig is auto-merged; context: `kind-kubelingo`
- Verify: `kubectl --context kind-kubelingo get nodes`
- Delete: `kind delete cluster --name kubelingo`

Pros: very fast, minimal footprint, safe to nuke/recreate. Cons: needs Docker/Podman; no built-in load balancer (use `kubectl port-forward` or `ingress-nginx` if needed).

### 2) k3d ( k3s in Docker )
Ultralight alternative using `k3s` in containers.

- Install: `brew install k3d` (macOS), or see https://k3d.io
- Create: `k3d cluster create kubelingo`
- Use: context is merged into kubeconfig; `kubectl get nodes`
- Delete: `k3d cluster delete kubelingo`

Pros: tiny footprint, fast. Cons: needs Docker; slightly different defaults vs upstream Kubernetes (still excellent for learning).

### 3) Minikube
Flexible single-node cluster; works with Docker, HyperKit, Hyper-V, etc.

- Install: `brew install minikube` (macOS) or see https://minikube.sigs.k8s.io
- Start: `minikube start --cpus=2 --memory=4g`
- Context: switched automatically to `minikube`; verify with `kubectl get nodes`
- Delete: `minikube delete`

Pros: broad OS/driver support, built-in addons. Cons: can be heavier than kind/k3d depending on driver.

### 4) Rancher Desktop (GUI)
Zero-CLI setup on macOS/Windows. Uses containerd by default.

- Install: https://rancherdesktop.io
- Enable Kubernetes in the UI and wait for “Running”.
- `kubectl config current-context` should show a Rancher Desktop context.
- Uninstall or disable Kubernetes to reclaim resources.

Pros: easy, polished UI. Cons: background footprint; fewer knobs than DIY tools.

### 5) Docker Desktop Kubernetes (GUI)
If you already use Docker Desktop on macOS/Windows.

- Enable Kubernetes in Settings → Kubernetes → Enable.
- Wait for it to start; context is set automatically.
- Disable to stop; reset Kubernetes to clean slate if needed.

Pros: convenient if Docker Desktop is installed. Cons: resource usage; not available on Linux.

### 6) MicroK8s (Linux)
Lightweight, near-bare‑metal feel, great on Ubuntu.

- Install (Ubuntu): `sudo snap install microk8s --classic`
- Add user to group: `sudo usermod -aG microk8s $USER && newgrp microk8s`
- Enable basics: `microk8s enable dns storage`
- Kubeconfig: `microk8s config > ~/.kube/config` (or merge with existing)
- Stop/Delete: `microk8s stop` / `sudo snap remove microk8s`

Pros: low overhead, fast. Cons: Linux-only; uses snap.

## Cloud Options (Realistic, Mind Costs)
Cloud clusters feel like production but can incur charges. Prefer free trial credits and always delete clusters quickly.

### Google Kubernetes Engine (GKE)
- Autopilot mode simplifies node management and can be cost-efficient for short sessions.
- Create (Autopilot example):
  - `gcloud container clusters create-auto kubelingo --region <region>`
  - `gcloud container clusters get-credentials kubelingo --region <region>`
- Delete: `gcloud container clusters delete kubelingo --region <region>`

### Azure Kubernetes Service (AKS)
- Control plane is managed; you pay for nodes (including while idle).
- Create (small dev cluster):
  - `az group create -n kubelingo-rg -l <region>`
  - `az aks create -g kubelingo-rg -n kubelingo --node-count 1 --node-vm-size Standard_B2s`
  - `az aks get-credentials -g kubelingo-rg -n kubelingo`
- Delete: `az group delete -n kubelingo-rg --yes --no-wait`

### Amazon EKS
- Managed control plane plus worker nodes or Fargate. Be mindful of per‑cluster and compute costs.
- Create (eksctl example):
  - `eksctl create cluster --name kubelingo --region <region> --nodes 1 --node-type t3.small`
- Delete: `eksctl delete cluster --name kubelingo --region <region>`

Cost tips:
- Prefer the smallest instance types and single-node clusters for short labs.
- Use per‑pod models (e.g., Autopilot/Fargate) for brief sessions; delete immediately after.
- Always verify deletion completed to stop billing.

## Using Kubelingo With Your Cluster
- Ensure `kubectl` points at the intended context and namespace before answering.
- For command questions, run the command exactly as you would in the exam. Add `--namespace kubelingo-lab` if you didn’t set the namespace on the context.
- For YAML questions, you can apply your manifest to the lab namespace to validate:
  - `kubectl apply -f answer.yaml`
  - Inspect with `kubectl get/describe/logs` as required.
- Clean up between questions to keep things tidy:
  - `kubectl delete -f answer.yaml` or recreate the namespace for an isolated reset.

## Troubleshooting
- Context mix‑ups: `kubectl config get-contexts` and `kubectl config use-context <name>`.
- Permissions: on local clusters you’re usually admin; on cloud, ensure your IAM and RBAC allow resource creation in your chosen namespace.
- Resource pressure: reduce replicas or requests/limits for small nodes; many labs work with `replicas: 1`.
- Ingress/LoadBalancer: for local clusters use `kubectl port-forward` or install an ingress controller and/or a local load balancer addon.

## What’s Easiest and Cheapest?
- Easiest overall: Rancher Desktop (GUI) or Docker Desktop (if already installed).
- Cheapest and fastest to reset: `kind` or `k3d`.
- Most realistic: short‑lived GKE Autopilot/AKS/EKS clusters using free credits, deleted right after practice.

Pick one that matches your OS and comfort level, set a dedicated namespace, and you’re ready to learn.

