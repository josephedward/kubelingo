![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/multi_container&empty)
# Multi-container Pods (10%)

### Create a Pod with two containers, both with image busybox and command "echo hello; sleep 3600". Connect to the second container and run 'ls'

<details><summary>show</summary>
<p>

The easiest way to do it is create a pod with a single container and save its definition in a YAML file:

```bash
kubectl run busybox --image=busybox --restart=Never -o yaml --dry-run=client -- /bin/sh -c 'echo hello;sleep 3600' > pod.yaml
vi pod.yaml
```

Copy/paste the container related values, so your final YAML should contain the following two containers (make sure those containers have a different name):

```YAML
containers:
  - args:
    - /bin/sh
    - -c
    - echo hello;sleep 3600
    image: busybox
    imagePullPolicy: IfNotPresent
    name: busybox
    resources: {}
  - args:
    - /bin/sh
    - -c
    - echo hello;sleep 3600
    image: busybox
    name: busybox2
```

```bash
kubectl create -f pod.yaml
# Connect to the busybox2 container within the pod
kubectl exec -it busybox -c busybox2 -- /bin/sh
ls
exit

# or you can do the above with just a one-liner
kubectl exec -it busybox -c busybox2 -- ls

# you can do some cleanup
kubectl delete po busybox
```

</p>
</details>

### Create a pod with an nginx container exposed on port 80 and add a busybox init container that performs the command "echo 'Test' > /work-dir/index.html". To share data between the init container and the nginx container, use a volume of type emptyDir. Mount this volume at "/work-dir" in the init container and at "/usr/share/nginx/html" in the nginx container to replace the default nginx webpage. After setting up the pod, determine its IP address. Then, create a separate pod with a busybox container and execute the command "wget -O- [IP of the first pod]" to download and display the content served by the nginx container.

<details><summary>show</summary>
<p>

The easiest way to do it is create a pod with a single container and save its definition in a YAML file:

```bash
kubectl run box --image=nginx --restart=Never --port=80 --dry-run=client -o yaml > pod-init.yaml
```

Copy/paste the container related values, so your final YAML should contain the volume and the initContainer:

Volume:

```YAML
containers:
- image: nginx
...
  volumeMounts:
  - name: vol
    mountPath: /usr/share/nginx/html
volumes:
- name: vol
  emptyDir: {}
```

initContainer:

```YAML
...
initContainers:
- args:
  - /bin/sh
  - -c
  - echo "Test" > /work-dir/index.html
  image: busybox
  name: box
  volumeMounts:
  - name: vol
    mountPath: /work-dir
```

In total you get:

```YAML

apiVersion: v1
kind: Pod
metadata:
  labels:
    run: box
  name: box
spec:
  initContainers: 
  - args: 
    - /bin/sh 
    - -c 
    - echo "Test" > /work-dir/index.html
    image: busybox 
    name: box 
    volumeMounts: 
    - name: vol 
      mountPath: /work-dir 
  containers:
  - image: nginx
    name: nginx
    ports:
    - containerPort: 80
    volumeMounts: 
    - name: vol 
      mountPath: /usr/share/nginx/html 
  volumes: 
  - name: vol 
    emptyDir: {} 
```

```bash
# Apply pod
kubectl apply -f pod-init.yaml

# Get IP
kubectl get po -o wide

# Execute wget
kubectl run box-test --image=busybox --restart=Never -it --rm -- /bin/sh -c "wget -O- $(kubectl get pod box -o jsonpath='{.status.podIP}')"

# you can do some cleanup
kubectl delete po box
```

</p>
</details>

