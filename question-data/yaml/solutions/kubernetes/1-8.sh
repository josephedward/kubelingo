kubectl get deployment frontend -o jsonpath='{.spec.paused}' | grep true
