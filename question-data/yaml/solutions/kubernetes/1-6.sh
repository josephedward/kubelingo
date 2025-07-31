kubectl get deployment nginx -o jsonpath='{.metadata.annotations.kubernetes\.io/change-cause}' | grep 'kubectl create'
