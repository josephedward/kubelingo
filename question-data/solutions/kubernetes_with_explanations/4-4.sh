kubectl run app --image=nginx --dry-run=client -o yaml > pod.yaml # add envFrom with configMapRef
