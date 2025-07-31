kubectl apply -f pod.yaml && kubectl get pod secret-pod -o jsonpath='{.spec.volumes[0].secret.secretName}' | grep 'my-secret'
