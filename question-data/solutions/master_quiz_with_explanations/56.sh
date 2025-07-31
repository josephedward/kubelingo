kubectl run secret-pod --image=nginx --dry-run=client -o yaml > pod.yaml # add volume.secret
