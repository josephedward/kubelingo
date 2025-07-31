kubectl apply -f pod.yaml && kubectl get pod secure-app -o yaml | grep 'secretKeyRef'
