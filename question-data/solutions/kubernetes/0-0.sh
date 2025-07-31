#!/bin/bash
set -e
POD_NAME=$(kubectl get pod nginx -o jsonpath='{.metadata.name}' 2>/dev/null)
if [ "$POD_NAME" != "nginx" ]; then
  echo "Error: Pod 'nginx' not found."
  exit 1
fi
IMAGE=$(kubectl get pod nginx -o jsonpath='{.spec.containers[0].image}')
if [ "$IMAGE" != "nginx" ]; then
  echo "Error: Image is '$IMAGE', expected 'nginx'."
  exit 1
fi
PORT=$(kubectl get pod nginx -o jsonpath='{.spec.containers[0].ports[0].containerPort}')
if [ "$PORT" != "80" ]; then
  echo "Error: Port is '$PORT', expected '80'."
  exit 1
fi
echo "Pod 'nginx' with image 'nginx' and port 80 found."
