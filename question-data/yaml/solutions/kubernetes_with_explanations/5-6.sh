kubectl run secure-app --image=nginx --dry-run=client -o yaml > pod.yaml # add env.secretKeyRef
