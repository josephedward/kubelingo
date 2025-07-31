kubectl get configmap app-config -o jsonpath='{.data.config\.yaml}' | grep 'key: value'
