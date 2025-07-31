#!/bin/bash
set -e
kubectl apply -f resources.yaml
# Check ConfigMap data
DATA=$(kubectl get cm app-config -o jsonpath='{.data.index\.html}')
if ! echo "$DATA" | grep -q 'Hello World'; then
  echo "Error: ConfigMap 'app-config' does not have the correct data."
  exit 1
fi
# Wait for pod to be ready
kubectl wait --for=condition=Ready pod/web-server --timeout=120s > /dev/null
# Check that the mounted file contains the correct content
CONTENT=$(kubectl exec web-server -- curl -s localhost)
if ! echo "$CONTENT" | grep -q 'Hello World'; then
  echo "Error: The web server did not return the expected content from the ConfigMap."
  echo "Received: $CONTENT"
  exit 1
fi
echo "Pod is serving content from the mounted ConfigMap correctly."
