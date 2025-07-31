#!/bin/bash
set -e
kubectl apply -f service.yaml
kubectl wait --for=condition=available deployment/webapp --timeout=60s > /dev/null
# Check service exists and is NodePort
TYPE=$(kubectl get svc webapp-svc -o jsonpath='{.spec.type}')
if [ "$TYPE" != "NodePort" ]; then
  echo "Error: Service 'webapp-svc' is type '$TYPE', expected 'NodePort'"
  exit 1
fi
# Check service port and targetPort
PORT=$(kubectl get svc webapp-svc -o jsonpath='{.spec.ports[0].port}')
TARGET_PORT=$(kubectl get svc webapp-svc -o jsonpath='{.spec.ports[0].targetPort}')
if [ "$PORT" != "80" ]; then
  echo "Error: Service port is '$PORT', expected '80'"
  exit 1
fi
if [ "$TARGET_PORT" != "8080" ]; then
  echo "Error: Service targetPort is '$TARGET_PORT', expected '8080'"
  exit 1
fi
echo "Service 'webapp-svc' correctly configured as a NodePort."
