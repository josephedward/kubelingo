![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/core_concepts&empty)
# Core Concepts (13%)

kubernetes.io > Documentation > Reference > kubectl CLI > [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

kubernetes.io > Documentation > Tasks > Monitoring, Logging, and Debugging > [Get a Shell to a Running Container](https://kubernetes.io/docs/tasks/debug-application-cluster/get-shell-running-container/)

kubernetes.io > Documentation > Tasks > Access Applications in a Cluster > [Configure Access to Multiple Clusters](https://kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/)

kubernetes.io > Documentation > Tasks > Access Applications in a Cluster > [Accessing Clusters](https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/) using API

kubernetes.io > Documentation > Tasks > Access Applications in a Cluster > [Use Port Forwarding to Access Applications in a Cluster](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/)

---
validation_steps:
  - cmd: "kubectl get ns mynamespace"
    matcher:
      exit_code: 0
  - cmd: "kubectl get pod nginx -n mynamespace"
    matcher:
      exit_code: 0
---
### Create a namespace called 'mynamespace' and a pod with image nginx called nginx on this namespace

<details><summary>show</summary>
<p>

```bash
kubectl create namespace mynamespace
kubectl run nginx --image=nginx --restart=Never -n mynamespace
```

</p>
</details>

---
pre_shell_cmds:
  - "kubectl create ns mynamespace"
validation_steps:
  - cmd: "test -f pod.yaml"
    matcher:
      exit_code: 0
  - cmd: "kubectl get pod nginx -n mynamespace"
    matcher:
      exit_code: 0
---
### Create a pod with the image nginx called nginx in a namespace called 'mynamespace' using YAML.

<details><summary>show</summary>
<p>

Easily generate YAML with:

```bash
kubectl run nginx --image=nginx --restart=Never --dry-run=client -n mynamespace -o yaml > pod.yaml
```

```bash
cat pod.yaml
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
  namespace: mynamespace
spec:
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
```

Alternatively, you can run in one line

```bash
kubectl run nginx --image=nginx --restart=Never --dry-run=client -o yaml | kubectl create -n mynamespace -f -
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create a busybox pod using the kubectl command that runs the command "env". Ensure the pod is named 'busybox' and it is created in the same namespace ('mynamespace') as the nginx pod specified in the previous task. Run the pod and see the output.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --image=busybox --command --restart=Never -it --rm -- env # -it will help in seeing the output, --rm will immediately delete the pod after it exits
# or, just run it without -it
kubectl run busybox --image=busybox --command --restart=Never -- env
# and then, check its logs
kubectl logs busybox
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create a busybox pod using YAML that runs the command "env" and is placed in the 'mynamespace' namespace, similar to the nginx pod created in a previous task. Run the pod and see the output.

<details><summary>show</summary>
<p>

```bash
# create a  YAML template with this command
kubectl run busybox --image=busybox --restart=Never --dry-run=client -o yaml --command -- env > envpod.yaml
# see it
cat envpod.yaml
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: busybox
  name: busybox
spec:
  containers:
  - command:
    - env
    image: busybox
    name: busybox
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
# apply it and then see the logs
kubectl apply -f envpod.yaml
kubectl logs busybox
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Get the YAML definition for a new namespace called 'myns' without actually creating the namespace. This follows a previous task where you created a busybox pod that runs the command "env" and is placed in the 'mynamespace' namespace using YAML.

<details><summary>show</summary>
<p>

```bash
kubectl create namespace myns -o yaml --dry-run=client
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create the YAML definition for a new ResourceQuota called 'myrq' in the namespace 'myns', where you previously created a busybox pod that runs the command "env". The ResourceQuota should have hard limits of 1 CPU, 1G memory, and allow for a maximum of 2 pods, all without actually creating the ResourceQuota.

<details><summary>show</summary>
<p>

```bash
kubectl create quota myrq --hard=cpu=1,memory=1G,pods=2 --dry-run=client -o yaml
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### List all pods across all namespaces in the Kubernetes cluster where you've been working with ResourceQuotas and pods, including the one running the busybox image.

<details><summary>show</summary>
<p>

```bash
kubectl get po --all-namespaces
```
Alternatively 

```bash
kubectl get po -A
```
</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create a pod in the Kubernetes cluster with the image nginx, name the pod nginx, and expose it to receive traffic on port 80.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --restart=Never --port=80
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### After creating a pod in the Kubernetes cluster with the image nginx, naming the pod nginx, and exposing it to receive traffic on port 80, change the pod's image to nginx:1.24.0. Observe that the container will be restarted as soon as the image gets pulled.

<details><summary>show</summary>
<p>

```bash
# kubectl set image POD/POD_NAME CONTAINER_NAME=IMAGE_NAME:TAG
kubectl set image pod/nginx nginx=nginx:1.24.0
kubectl describe po nginx # you will see an event 'Container will be killed and recreated'
kubectl get po nginx -w # watch it
```

*Note*: The `RESTARTS` column should contain 0 initially (ideally - it could be any number)

*Note*: some time after changing the image, you should see that the value in the `RESTARTS` column has been increased by 1, because the container has been restarted, as stated in the events shown at the bottom of the `kubectl describe pod` command:

```
Events:
  Type    Reason     Age                  From               Message
  ----    ------     ----                 ----               -------
[...]
  Normal  Killing    100s                 kubelet, node3     Container pod1 definition changed, will be restarted
  Normal  Pulling    100s                 kubelet, node3     Pulling image "nginx:1.24.0"
  Normal  Pulled     41s                  kubelet, node3     Successfully pulled image "nginx:1.24.0"
  Normal  Created    36s (x2 over 9m43s)  kubelet, node3     Created container pod1
  Normal  Started    36s (x2 over 9m43s)  kubelet, node3     Started container pod1
```

*Note*: you can check pod's image by running

```bash
kubectl get po nginx -o jsonpath='{.spec.containers[].image}{"\n"}'
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### After creating a pod in the Kubernetes cluster with the image nginx, naming the pod nginx, and exposing it to receive traffic on port 80, then changing the pod's image to nginx:1.24.0 and observing that the container restarts as soon as the image is pulled, get the nginx pod's IP and use a temporary busybox image to wget its root directory ('/').

<details><summary>show</summary>
<p>

```bash
kubectl get po -o wide # get the IP, will be something like '10.1.1.131'
# create a temp busybox pod
kubectl run busybox --image=busybox --rm -it --restart=Never -- wget -O- 10.1.1.131:80
```

Alternatively you can also try a more advanced option:

```bash
# Get IP of the nginx pod
NGINX_IP=$(kubectl get pod nginx -o jsonpath='{.status.podIP}')
# create a temp busybox pod
kubectl run busybox --image=busybox --env="NGINX_IP=$NGINX_IP" --rm -it --restart=Never -- sh -c 'wget -O- $NGINX_IP:80'
``` 

Or just in one line:

```bash
kubectl run busybox --image=busybox --rm -it --restart=Never -- wget -O- $(kubectl get pod nginx -o jsonpath='{.status.podIP}:{.spec.containers[0].ports[0].containerPort}')
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Retrieve the YAML configuration of the nginx pod, which was initially created with the nginx image, named nginx, exposed to receive traffic on port 80, and later had its image updated to nginx:1.24.0.

<details><summary>show</summary>
<p>

```bash
kubectl get po nginx -o yaml
# or
kubectl get po nginx -oyaml
# or
kubectl get po nginx --output yaml
# or
kubectl get po nginx --output=yaml
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Get information about the nginx pod, which was initially created with the nginx image, named nginx, exposed to receive traffic on port 80, and later had its image updated to nginx:1.24.0, including details about potential issues (e.g., pod hasn't started).

<details><summary>show</summary>
<p>

```bash
kubectl describe po nginx
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Get the logs of the nginx pod, named nginx, which was initially created with the nginx image, then updated to use the nginx:1.24.0 image, and is exposed to receive traffic on port 80.

<details><summary>show</summary>
<p>

```bash
kubectl logs nginx
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### If the nginx pod, named nginx, which was initially created with the nginx image, then updated to use the nginx:1.24.0 image, and is exposed to receive traffic on port 80, crashed and restarted, get logs about the previous instance.

<details><summary>show</summary>
<p>

```bash
kubectl logs nginx -p
# or
kubectl logs nginx --previous
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Execute a simple shell command on the nginx pod, which was initially created with the nginx image and then updated to use the nginx:1.24.0 image, and is exposed to receive traffic on port 80.

<details><summary>show</summary>
<p>

```bash
kubectl exec -it nginx -- /bin/sh
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create a busybox pod that echoes 'hello world' and then exits, ensuring it is separate from the nginx pod initially created with the nginx image and later updated to use the nginx:1.24.0 image, which is exposed to receive traffic on port 80.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --image=busybox -it --restart=Never -- echo 'hello world'
# or
kubectl run busybox --image=busybox -it --restart=Never -- /bin/sh -c 'echo hello world'
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create a busybox pod that echoes 'hello world' and then exits, ensuring it is separate from an initially created nginx pod that was later updated to use the nginx:1.24.0 image and exposed to receive traffic on port 80. Additionally, configure the busybox pod to be deleted automatically once it has completed its task.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --image=busybox -it --rm --restart=Never -- /bin/sh -c 'echo hello world'
kubectl get po # nowhere to be found :)
```

</p>
</details>

---
validation_steps:
  - cmd: "true"
    matcher:
      exit_code: 0
---
### Create an nginx pod, separate from the busybox pod that echoes 'hello world' and then exits. Ensure this nginx pod is set with an environment variable 'var1=val1' and verify the existence of this environment variable within the pod.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --restart=Never --env=var1=val1
# then
kubectl exec -it nginx -- env
# or
kubectl exec -it nginx -- sh -c 'echo $var1'
# or
kubectl describe po nginx | grep val1
# or
kubectl run nginx --restart=Never --image=nginx --env=var1=val1 -it --rm -- env
# or
kubectl run nginx --image nginx --restart=Never --env=var1=val1 -it --rm -- sh -c 'echo $var1'
```

</p>
</details>
