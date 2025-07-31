kubectl get deployment frontend -o jsonpath='{.spec.replicas}' | grep 3
