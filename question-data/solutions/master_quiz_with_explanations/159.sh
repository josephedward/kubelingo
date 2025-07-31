kubectl run config-pod --image=nginx --dry-run=client -o yaml > pod.yaml # then add volume with defaultMode
