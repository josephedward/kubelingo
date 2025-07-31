kubectl apply -f pod.yaml && kubectl get pod config-pod -o jsonpath='{.spec.volumes[0].configMap.name}' | grep 'my-cm'
