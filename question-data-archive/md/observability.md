![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/observability&empty)
# Observability (18%)

## Liveness, readiness and startup probes

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

### Create an nginx pod with a liveness probe that just runs the command 'ls'. Save its YAML in pod.yaml. Run it, check its probe status, delete it.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --restart=Never --dry-run=client -o yaml > pod.yaml
vi pod.yaml
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
spec:
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
    livenessProbe: # our probe
      exec: # add this line
        command: # command definition
        - ls # ls command
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl describe pod nginx | grep -i liveness # run this to see that liveness probe works
kubectl delete -f pod.yaml
```

</p>
</details>

### Modify the YAML configuration of an nginx pod that you previously created with a liveness probe running the command 'ls'. Adjust the liveness probe in the pod.yaml file to start after 5 seconds and set the interval between probes to 5 seconds. After making these adjustments, run the updated pod, check its liveness probe status to ensure it is working as expected, then delete the pod.

<details><summary>show</summary>
<p>

```bash
kubectl explain pod.spec.containers.livenessProbe # get the exact names
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
spec:
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
    livenessProbe:
      initialDelaySeconds: 5 # add this line
      periodSeconds: 5 # add this line as well
      exec:
        command:
        - ls
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl describe po nginx | grep -i liveness
kubectl delete -f pod.yaml
```

</p>
</details>

### Create an nginx pod (that includes port 80) with an HTTP readinessProbe configured to check the path '/' on port 80. After creation, run this pod, verify the functionality of the readinessProbe by checking its status to ensure it is working as expected, then delete the pod. This question follows the previous task where you modified a YAML configuration for an nginx pod by adjusting a liveness probe; now you'll focus on implementing and testing a readinessProbe.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --dry-run=client -o yaml --restart=Never --port=80 > pod.yaml
vi pod.yaml
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
spec:
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
    ports:
    - containerPort: 80 # Note: Readiness probes runs on the container during its whole lifecycle. Since nginx exposes 80, containerPort: 80 is not required for readiness to work.
    readinessProbe: # declare the readiness probe
      httpGet: # add this line
        path: / #
        port: 80 #
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl describe pod nginx | grep -i readiness # to see the pod readiness details
kubectl delete -f pod.yaml
```

</p>
</details>

### Following the task where you created an nginx pod with a readinessProbe on port 80, now turn your attention to the broader cluster environment. Within the `qa`, `alan`, `test`, and `production` namespaces, all pods are configured with liveness probes. Please list all pods whose liveness probes have failed, providing the output in the format of `<namespace>/<pod name>` per line.

<details><summary>show</summary>
<p>

A typical liveness probe failure event
```
LAST SEEN   TYPE      REASON      OBJECT              MESSAGE
22m         Warning   Unhealthy   pod/liveness-exec   Liveness probe failed: cat: can't open '/tmp/healthy': No such file or directory
```

collect failed pods namespace by namespace

```sh
kubectl get events -o json | jq -r '.items[] | select(.message | contains("Liveness probe failed")).involvedObject | .namespace + "/" + .name'
```

</p>
</details>

## Logging

### Create a busybox pod in any namespace that runs the following command: `i=0; while true; do echo "$i: $(date)"; i=$((i+1)); sleep 1; done`. After deployment, check and provide its logs.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --image=busybox --restart=Never -- /bin/sh -c 'i=0; while true; do echo "$i: $(date)"; i=$((i+1)); sleep 1; done'
kubectl logs busybox -f # follow the logs
```

</p>
</details>

## Debugging

### Create a busybox pod in any namespace that runs the command `ls /notexist`. Check the logs to determine if there's an error (there will be an error). After reviewing the error in the logs, delete the pod.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --restart=Never --image=busybox -- /bin/sh -c 'ls /notexist'
# show that there's an error
kubectl logs busybox
kubectl describe po busybox
kubectl delete po busybox
```

</p>
</details>

### Create a busybox pod in any namespace that runs the command `ls /notexist`, similar to a previous task. Check the pod's logs to determine if there's an error (as expected, there will be an error). After observing the error, delete the pod forcefully using a 0 grace period.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --restart=Never --image=busybox -- notexist
kubectl logs busybox # will bring nothing! container never started
kubectl describe po busybox # in the events section, you'll see the error
# also...
kubectl get events | grep -i error # you'll see the error here as well
kubectl delete po busybox --force --grace-period=0
```

</p>
</details>


### Get CPU/memory utilization for nodes in the cluster (ensure that [metrics-server](https://github.com/kubernetes-incubator/metrics-server) is installed and running) after completing the task of creating a busybox pod in any namespace that runs the command `ls /notexist`, checking the pod's logs for an expected error, and forcefully deleting the pod with a 0 grace period.

<details><summary>show</summary>
<p>

```bash
kubectl top nodes
```

</p>
</details>
