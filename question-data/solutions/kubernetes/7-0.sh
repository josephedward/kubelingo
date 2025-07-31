#!/bin/bash
set -e
kubectl apply -f pod.yaml
# Check pod name
POD_NAME=$(kubectl get pods -o jsonpath='{.items[0].metadata.name}')
if [ "$POD_NAME" != "nginx-live" ]; then
  echo "Error: Pod name is '$POD_NAME', expected 'nginx-live'"
  exit 1
fi
# Check image
IMAGE=$(kubectl get pod nginx-live -o jsonpath='{.spec.containers[0].image}')
if [ "$IMAGE" != "nginx:stable" ]; then
  echo "Error: Image is '$IMAGE', expected 'nginx:stable'"
  exit 1
fi
echo "Pod 'nginx-live' with image 'nginx:stable' found."
