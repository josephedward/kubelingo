kubectl get pod nginx -o jsonpath='{.spec.containers[0].env[0].value}' | grep 'postgresql://db'
