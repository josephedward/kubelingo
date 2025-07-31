test $(kubectl get deployment frontend -o jsonpath='{.spec.paused}') != 'true'
