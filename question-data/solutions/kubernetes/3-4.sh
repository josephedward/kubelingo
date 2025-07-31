kubectl apply -f pod.yaml && kubectl get pod my-pod -o yaml | grep 'configMapKeyRef'
