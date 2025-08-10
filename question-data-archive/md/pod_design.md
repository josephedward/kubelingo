![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/pod_design&empty)
# Pod design (20%)

[Labels And Annotations](#labels-and-annotations)

[Deployments](#deployments)

[Jobs](#jobs)

[Cron Jobs](#cron-jobs)

## Labels and Annotations
kubernetes.io > Documentation > Concepts > Overview > Working with Kubernetes Objects > [Labels and Selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#label-selectors)

### Create 3 pods with names nginx1,nginx2,nginx3. All of them should have the label app=v1

<details><summary>show</summary>
<p>

```bash
kubectl run nginx1 --image=nginx --restart=Never --labels=app=v1
kubectl run nginx2 --image=nginx --restart=Never --labels=app=v1
kubectl run nginx3 --image=nginx --restart=Never --labels=app=v1
# or
for i in `seq 1 3`; do kubectl run nginx$i --image=nginx -l app=v1 ; done
```

</p>
</details>

### Show all labels of the pods named nginx1, nginx2, and nginx3, which were created with the label app=v1.

<details><summary>show</summary>
<p>

```bash
kubectl get po --show-labels
```

</p>
</details>

### Change the labels of the pod named 'nginx2', which was originally created with the label app=v1, to be app=v2.

<details><summary>show</summary>
<p>

```bash
kubectl label po nginx2 app=v2 --overwrite
# or edit the pod yaml
kubectl edit po nginx2
```

</p>
</details>

### After changing the labels of the pod named 'nginx2', which was originally created with the label app=v1, to app=v2, retrieve the label 'app' for the pods by showing a column with APP labels.

<details><summary>show</summary>
<p>

```bash
kubectl get po -L app
# or
kubectl get po --label-columns=app
```

</p>
</details>

### Retrieve only the pods labeled with 'app=v2', assuming a scenario where the label of a pod named 'nginx2', originally labeled 'app=v1', was changed to 'app=v2'.

<details><summary>show</summary>
<p>

```bash
kubectl get po -l app=v2
# or
kubectl get po -l 'app in (v2)'
# or
kubectl get po --selector=app=v2
```

</p>
</details>

### Retrieve only the pods labeled with 'app=v2' but exclude those labeled with 'tier=frontend', including a scenario where a pod named 'nginx2' was originally labeled 'app=v1' and then had its label changed to 'app=v2'.

<details><summary>show</summary>
<p>

```bash
kubectl get po -l app=v2,tier!=frontend
# or
kubectl get po -l 'app in (v2), tier notin (frontend)'
# or
kubectl get po --selector=app=v2,tier!=frontend
```

</p>
</details>

### Add a new label tier=web to all pods initially labeled with either 'app=v1' or 'app=v2', including pods like 'nginx2' which was originally labeled 'app=v1' but then had its label changed to 'app=v2'.

<details><summary>show</summary>
<p>

```bash
kubectl label po -l "app in(v1,v2)" tier=web
```
</p>
</details>


### Add an annotation 'owner: marketing' to all pods initially labeled with either 'app=v1' or 'app=v2', including pods like 'nginx2' which was originally labeled 'app=v1' but then had its label changed to 'app=v2', currently having 'app=v2' label.

<details><summary>show</summary>
<p>

```bash
kubectl annotate po -l "app=v2" owner=marketing
```
</p>
</details>

### Remove the 'app' label from all pods that were initially labeled with either 'app=v1' or 'app=v2' and had the annotation 'owner: marketing' added, including pods like those initially labeled 'app=v1' but then had their label changed to 'app=v2'.

<details><summary>show</summary>
<p>

```bash
kubectl label po nginx1 nginx2 nginx3 app-
# or
kubectl label po nginx{1..3} app-
# or
kubectl label po -l app app-
```

</p>
</details>

### Annotate pods nginx1, nginx2, nginx3, which are among the pods that had either 'app=v1' or 'app=v2' labels and were annotated with 'owner: marketing', with "description='my description'" value.

<details><summary>show</summary>
<p>


```bash
kubectl annotate po nginx1 nginx2 nginx3 description='my description'

#or

kubectl annotate po nginx{1..3} description='my description'
```

</p>
</details>

### Check the annotations for pod nginx1, ensuring it includes the "description='my description'" value, following its annotation along with pods nginx2 and nginx3, which had been previously selected for annotation because they had either 'app=v1' or 'app=v2' labels and were also annotated with 'owner: marketing'.

<details><summary>show</summary>
<p>

```bash
kubectl annotate pod nginx1 --list

# or

kubectl describe po nginx1 | grep -i 'annotations'

# or

kubectl get po nginx1 -o custom-columns=Name:metadata.name,ANNOTATIONS:metadata.annotations.description
```

As an alternative to using `| grep` you can use jsonPath like `kubectl get po nginx1 -o jsonpath='{.metadata.annotations}{"\n"}'`

</p>
</details>

### Remove the annotations for the three pods, nginx1, nginx2, and nginx3, previously annotated because they either had 'app=v1' or 'app=v2' labels and were annotated with 'owner: marketing', including ensuring that nginx1's annotation also had the "description='my description'" value.

<details><summary>show</summary>
<p>

```bash
kubectl annotate po nginx{1..3} description- owner-
```

</p>
</details>

### Remove the three pods named nginx1, nginx2, and nginx3 from your cluster to ensure a clean state, following their previous annotation updates due to having either 'app=v1' or 'app=v2' labels and a specific annotation for nginx1 with 'owner: marketing' and "description='my description'".

<details><summary>show</summary>
<p>

```bash
kubectl delete po nginx{1..3}
```

</p>
</details>

## Pod Placement

### Create a pod that will be deployed to a Node that has the label 'accelerator=nvidia-tesla-p100', considering you have just ensured a clean state by removing three pods named nginx1, nginx2, and nginx3 from your cluster following updates to their annotations and labels.

<details><summary>show</summary>
<p>

Add the label to a node:

```bash
kubectl label nodes <your-node-name> accelerator=nvidia-tesla-p100
kubectl get nodes --show-labels
```

We can use the 'nodeSelector' property on the Pod YAML:

```YAML
apiVersion: v1
kind: Pod
metadata:
  name: cuda-test
spec:
  containers:
    - name: cuda-test
      image: "k8s.gcr.io/cuda-vector-add:v0.1"
  nodeSelector: # add this
    accelerator: nvidia-tesla-p100 # the selection label
```

You can easily find out where in the YAML it should be placed by:

```bash
kubectl explain po.spec
```

OR:
Use node affinity (https://kubernetes.io/docs/tasks/configure-pod-container/assign-pods-nodes-using-node-affinity/#schedule-a-pod-using-required-node-affinity)

```YAML
apiVersion: v1
kind: Pod
metadata:
  name: affinity-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: accelerator
            operator: In
            values:
            - nvidia-tesla-p100
  containers:
    ...
```

</p>
</details>

### Taint a node with the key `tier` and value `frontend` with the effect `NoSchedule`. Then, create a pod that tolerates this taint, ensuring that this new pod also meets the criterion from a previous task: it should be deployable to a Node that has the label `accelerator=nvidia-tesla-p100`.

<details><summary>show</summary>
<p>

Taint a node:

```bash
kubectl taint node node1 tier=frontend:NoSchedule # key=value:Effect
kubectl describe node node1 # view the taints on a node
```

And to tolerate the taint:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: frontend
spec:
  containers:
  - name: nginx
    image: nginx
  tolerations:
  - key: "tier"
    operator: "Equal"
    value: "frontend"
    effect: "NoSchedule"
```

</p>
</details>

### Create a pod that will be placed on the node `controlplane` by using nodeSelector to ensure it targets a node with the label `accelerator=nvidia-tesla-p100`. Additionally, the pod should include tolerations to allow it to be scheduled on a node tainted with the key `tier`, value `frontend`, and effect `NoSchedule`.

<details><summary>show</summary>
<p>

```bash
vi pod.yaml
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: frontend
spec:
  containers:
  - name: nginx
    image: nginx
  nodeSelector:
    kubernetes.io/hostname: controlplane
  tolerations:
  - key: "node-role.kubernetes.io/control-plane"
    operator: "Exists"
    effect: "NoSchedule"
```

```bash
kubectl create -f pod.yaml
```

</p>
</details>

## Deployments

kubernetes.io > Documentation > Concepts > Workloads > Workload Resources > [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment)

### Create a deployment called nginx, using the image nginx:1.18.0, with 2 replicas. Define port 80 as the port that the container exposes. This deployment should also include specifications so that pods are placed on a node labeled with `accelerator=nvidia-tesla-p100` by using a nodeSelector, and include tolerations to allow the pods to be scheduled on a node tainted with the key `tier`, value `frontend`, and effect `NoSchedule`. Do not create a service for this deployment.

<details><summary>show</summary>
<p>

```bash
kubectl create deployment nginx  --image=nginx:1.18.0  --dry-run=client -o yaml > deploy.yaml
vi deploy.yaml
# change the replicas field from 1 to 2
# add this section to the container spec and save the deploy.yaml file
# ports:
#   - containerPort: 80
kubectl apply -f deploy.yaml
```

or, do something like:

```bash
kubectl create deployment nginx  --image=nginx:1.18.0  --dry-run=client -o yaml | sed 's/replicas: 1/replicas: 2/g'  | sed 's/image: nginx:1.18.0/image: nginx:1.18.0\n        ports:\n        - containerPort: 80/g' | kubectl apply -f -
```

or,
```bash
kubectl create deploy nginx --image=nginx:1.18.0 --replicas=2 --port=80
```

</p>
</details>

### View the YAML of the deployment called nginx, which uses the image nginx:1.18.0, with 2 replicas, defines port 80 as the port that the container exposes, includes a nodeSelector to place pods on a node labeled with `accelerator=nvidia-tesla-p100`, and includes tolerations to allow the pods to be scheduled on a node tainted with the key `tier`, value `frontend`, and effect `NoSchedule`.

<details><summary>show</summary>
<p>

```bash
kubectl get deploy nginx -o yaml
```

</p>
</details>

### View the YAML of the replica set that was created by the deployment called nginx, which uses the image nginx:1.18.0, with 2 replicas, defines port 80 as the port that the container exposes, includes a nodeSelector to place pods on a node labeled with `accelerator=nvidia-tesla-p100`, and includes tolerations to allow the pods to be scheduled on a node tainted with the key `tier`, value `frontend`, and effect `NoSchedule`.

<details><summary>show</summary>
<p>

```bash
kubectl describe deploy nginx # you'll see the name of the replica set on the Events section and in the 'NewReplicaSet' property
# OR you can find rs directly by:
kubectl get rs -l run=nginx # if you created deployment by 'run' command
kubectl get rs -l app=nginx # if you created deployment by 'create' command
# you could also just do kubectl get rs
kubectl get rs nginx-7bf7478b77 -o yaml
```

</p>
</details>

### Get the YAML for one of the pods created by the deployment called nginx, which uses the image nginx:1.18.0, with 2 replicas, and defines port 80 as the port that the container exposes. This deployment also includes a nodeSelector to place pods on a node labeled with `accelerator=nvidia-tesla-p100` and includes tolerations to allow the pods to be scheduled on a node tainted with the key `tier`, value `frontend`, and effect `NoSchedule`.

<details><summary>show</summary>
<p>

```bash
kubectl get po # get all the pods
# OR you can find pods directly by:
kubectl get po -l run=nginx # if you created deployment by 'run' command
kubectl get po -l app=nginx # if you created deployment by 'create' command
kubectl get po nginx-7bf7478b77-gjzp8 -o yaml
```

</p>
</details>

### Check how the deployment rollout is going for the nginx deployment, which uses the image nginx:1.18.0, has 2 replicas, and defines port 80 as the container's exposed port, including a nodeSelector for nodes labeled with `accelerator=nvidia-tesla-p100` and tolerations for nodes tainted with `tier=frontend` and effect `NoSchedule`.

<details><summary>show</summary>
<p>

```bash
kubectl rollout status deploy nginx
```

</p>
</details>

### Update the nginx deployment, which uses the image nginx:1.18.0, has 2 replicas, and defines port 80 as the container's exposed port, with a nodeSelector for nodes labeled `accelerator=nvidia-tesla-p100` and tolerations for nodes tainted `tier=frontend` and effect `NoSchedule`, to use the nginx image version nginx:1.19.8.

<details><summary>show</summary>
<p>

```bash
kubectl set image deploy nginx nginx=nginx:1.19.8
# alternatively...
kubectl edit deploy nginx # change the .spec.template.spec.containers[0].image
```

The syntax of the 'kubectl set image' command is `kubectl set image (-f FILENAME | TYPE NAME) CONTAINER_NAME_1=CONTAINER_IMAGE_1 ... CONTAINER_NAME_N=CONTAINER_IMAGE_N [options]`

</p>
</details>

### After updating the nginx deployment to use the nginx image version nginx:1.19.8, check the rollout history of this deployment and confirm that the replicas are OK.

<details><summary>show</summary>
<p>

```bash
kubectl rollout history deploy nginx
kubectl get deploy nginx
kubectl get rs # check that a new replica set has been created
kubectl get po
```

</p>
</details>

### Undo the latest update to the nginx deployment, where the deployment was updated to use nginx image version nginx:1.19.8, and verify that new pods are using the previous image version, which is nginx:1.18.0.

<details><summary>show</summary>
<p>

```bash
kubectl rollout undo deploy nginx
# wait a bit
kubectl get po # select one 'Running' Pod
kubectl describe po nginx-5ff4457d65-nslcl | grep -i image # should be nginx:1.18.0
```

</p>
</details>

### Update the previously mentioned nginx deployment by intentionally using an incorrect image version, specifically nginx:1.91, and verify that the deployment reflects this update.

<details><summary>show</summary>
<p>

```bash
kubectl set image deploy nginx nginx=nginx:1.91
# or
kubectl edit deploy nginx
# change the image to nginx:1.91
# vim tip: type (without quotes) '/image' and press Enter, to navigate quickly
```

</p>
</details>

### Verify that something's wrong with the rollout after intentionally updating an nginx deployment with an incorrect image version, specifically nginx:1.91.

<details><summary>show</summary>
<p>

```bash
kubectl rollout status deploy nginx
# or
kubectl get po # you'll see 'ErrImagePull' or 'ImagePullBackOff'
```

</p>
</details>


### After intentionally updating an nginx deployment with an incorrect image version, specifically nginx:1.91, and verifying something is wrong with the rollout, return the deployment to the second revision (number 2) and verify the image is nginx:1.19.8.

<details><summary>show</summary>
<p>

```bash
kubectl rollout undo deploy nginx --to-revision=2
kubectl describe deploy nginx | grep Image:
kubectl rollout status deploy nginx # Everything should be OK
```

</p>
</details>

### Assuming you have previously updated an nginx deployment multiple times, including intentionally updating it with an incorrect image version and then correcting it, now check the details of the fourth revision (number 4) of this nginx deployment.

<details><summary>show</summary>
<p>

```bash
kubectl rollout history deploy nginx --revision=4 # You'll also see the wrong image displayed here
```

</p>
</details>

### Scale the nginx deployment, which you previously updated multiple times including intentionally updating it with an incorrect image version and then correcting it, to 5 replicas.

<details><summary>show</summary>
<p>

```bash
kubectl scale deploy nginx --replicas=5
kubectl get po
kubectl describe deploy nginx
```

</p>
</details>

### Autoscale the nginx deployment you previously updated multiple times, including intentionally updating it with an incorrect image version and then correcting it, setting the number of replicas to automatically adjust between 5 and 10, targeting CPU utilization at 80%

<details><summary>show</summary>
<p>

```bash
kubectl autoscale deploy nginx --min=5 --max=10 --cpu-percent=80
# view the horizontalpodautoscalers.autoscaling for nginx
kubectl get hpa nginx
```

</p>
</details>

### Pause the rollout of the nginx deployment you previously autoscaled, including during the process of intentionally updating it with an incorrect image version and then correcting it, specifying that the number of replicas should automatically adjust between 5 and 10, targeting CPU utilization at 80%.

<details><summary>show</summary>
<p>

```bash
kubectl rollout pause deploy nginx
```

</p>
</details>

### After pausing the rollout of the nginx deployment, which you previously autoscaled to automatically adjust the number of replicas between 5 and 10 based on a target CPU utilization of 80%, update the image to nginx:1.19.9 and verify that the rollout is indeed paused with no updates occurring.

<details><summary>show</summary>
<p>

```bash
kubectl set image deploy nginx nginx=nginx:1.19.9
# or
kubectl edit deploy nginx
# change the image to nginx:1.19.9
kubectl rollout history deploy nginx # no new revision
```

</p>
</details>

### After pausing the rollout of an nginx deployment that was previously autoscaled to automatically adjust the number of replicas between 5 and 10 based on a target CPU utilization of 80%, and updating the image to nginx:1.19.9 while verifying that the rollout is paused with no updates occurring, resume the rollout and check that the nginx:1.19.9 image has been applied.

<details><summary>show</summary>
<p>

```bash
kubectl rollout resume deploy nginx
kubectl rollout history deploy nginx
kubectl rollout history deploy nginx --revision=6 # insert the number of your latest revision
```

</p>
</details>

### Delete the nginx deployment that was paused during the rollout to update the image to nginx:1.19.9, and also delete the associated horizontal pod autoscaler that was configured to automatically adjust the number of replicas between 5 and 10 based on a target CPU utilization of 80%.

<details><summary>show</summary>
<p>

```bash
kubectl delete deploy nginx
kubectl delete hpa nginx

#Or
kubectl delete deploy/nginx hpa/nginx
```
</p>
</details>

### After deleting the nginx deployment that was paused during the rollout to update the image to nginx:1.19.9, along with its associated horizontal pod autoscaler configured to automatically adjust the number of replicas between 5 and 10 based on a target CPU utilization of 80%, implement canary deployment by running two instances of nginx marked as version=v1 and version=v2 so that the load is balanced at a 75%-25% ratio.

<details><summary>show</summary>
<p>

Deploy 3 replicas of v1:
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-v1
  labels:
    app: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
      version: v1
  template:
    metadata:
      labels:
        app: my-app
        version: v1
    spec:
      containers:
      - name: nginx
        image: nginx
        ports:
        - containerPort: 80
        volumeMounts:
        - name: workdir
          mountPath: /usr/share/nginx/html
      initContainers:
      - name: install
        image: busybox:1.28
        command:
        - /bin/sh
        - -c
        - "echo version-1 > /work-dir/index.html"
        volumeMounts:
        - name: workdir
          mountPath: "/work-dir"
      volumes:
      - name: workdir
        emptyDir: {}
```

Create the service:
```
apiVersion: v1
kind: Service
metadata:
  name: my-app-svc
  labels:
    app: my-app
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 80
    targetPort: 80
  selector:
    app: my-app
```

Test if the deployment was successful from within a Pod:
```
# run a wget to the Service my-app-svc
kubectl run -it --rm --restart=Never busybox --image=gcr.io/google-containers/busybox --command -- wget -qO- my-app-svc

version-1
```

Deploy 1 replica of v2:
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-v2
  labels:
    app: my-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
      version: v2
  template:
    metadata:
      labels:
        app: my-app
        version: v2
    spec:
      containers:
      - name: nginx
        image: nginx
        ports:
        - containerPort: 80
        volumeMounts:
        - name: workdir
          mountPath: /usr/share/nginx/html
      initContainers:
      - name: install
        image: busybox:1.28
        command:
        - /bin/sh
        - -c
        - "echo version-2 > /work-dir/index.html"
        volumeMounts:
        - name: workdir
          mountPath: "/work-dir"
      volumes:
      - name: workdir
        emptyDir: {}
```

Observe that calling the ip exposed by the service the requests are load balanced across the two versions:
```
# run a busyBox pod that will make a wget call to the service my-app-svc and print out the version of the pod it reached.
kubectl run -it --rm --restart=Never busybox --image=gcr.io/google-containers/busybox -- /bin/sh -c 'while sleep 1; do wget -qO- my-app-svc; done'

version-1
version-1
version-1
version-2
version-2
version-1
```

If the v2 is stable, scale it up to 4 replicas and shutdown the v1:
```
kubectl scale --replicas=4 deploy my-app-v2
kubectl delete deploy my-app-v1
while sleep 0.1; do curl $(kubectl get svc my-app-svc -o jsonpath="{.spec.clusterIP}"); done
version-2
version-2
version-2
version-2
version-2
version-2
```

</p>
</details>

## Jobs

### After implementing a canary deployment by running two instances of nginx marked as version=v1 and version=v2 with the load balanced at a 75%-25% ratio, following the deletion of the nginx deployment that was paused during the rollout to update its image to nginx:1.19.9 (along with its associated horizontal pod autoscaler configured to automatically adjust the number of replicas between 5 and 10 based on a target CPU utilization of 80%), now create a job named pi using the image perl:5.34. This job should execute the command with arguments "perl -Mbignum=bpi -wle 'print bpi(2000)'

<details><summary>show</summary>
<p>

```bash
kubectl create job pi  --image=perl:5.34 -- perl -Mbignum=bpi -wle 'print bpi(2000)'
```

</p>
</details>

### After the canary deployment process involving two nginx instances with versions v1 and v2 and the deletion of the nginx deployment updated to image nginx:1.19.9, and after creating a job named pi using the image perl:5.34 to execute the command "perl -Mbignum=bpi -wle 'print bpi(2000)'", wait until this job completes and then retrieve its output.

<details><summary>show</summary>
<p>

```bash
kubectl get jobs -w # wait till 'SUCCESSFUL' is 1 (will take some time, perl image might be big)
kubectl get po # get the pod name
kubectl logs pi-**** # get the pi numbers
kubectl delete job pi
```
OR

```bash
kubectl get jobs -w # wait till 'SUCCESSFUL' is 1 (will take some time, perl image might be big)
kubectl logs job/pi
kubectl delete job pi
```
OR

```bash
kubectl wait --for=condition=complete --timeout=300s job pi
kubectl logs job/pi
kubectl delete job pi
```

</p>
</details>

### Following the completion of tasks related to a canary deployment process involving nginx instances with versions v1 and v2, the deletion of the nginx deployment updated to image nginx:1.19.9, and the creation and completion of a job named pi using the image perl:5.34 to execute the command "perl -Mbignum=bpi -wle 'print bpi(2000)'" to retrieve its output, create a job using the image busybox that executes the command 'echo hello;sleep 30;echo world'.

<details><summary>show</summary>
<p>

```bash
kubectl create job busybox --image=busybox -- /bin/sh -c 'echo hello;sleep 30;echo world'
```

</p>
</details>

### After creating a job using the image busybox that executes the command 'echo hello;sleep 30;echo world' in the context of completing tasks for a canary deployment involving nginx instances and other specific Kubernetes operations, follow the logs for the pod, noting that you'll wait for 30 seconds.

<details><summary>show</summary>
<p>

```bash
kubectl get po # find the job pod
kubectl logs busybox-ptx58 -f # follow the logs
```

</p>
</details>

### After creating a job in Kubernetes using the image busybox with the command 'echo hello;sleep 30;echo world' in the context of a canary deployment operation involving nginx instances, check the status of this job, describe it, and view the logs of the pod generated by this job.

<details><summary>show</summary>
<p>

```bash
kubectl get jobs
kubectl describe jobs busybox
kubectl logs job/busybox
```

</p>
</details>

### Delete the job created in Kubernetes that uses the image busybox with the command 'echo hello;sleep 30;echo world' in the context of a canary deployment operation involving nginx instances.

<details><summary>show</summary>
<p>

```bash
kubectl delete job busybox
```

</p>
</details>

### Create a job in Kubernetes that uses the image busybox with the command 'echo hello;sleep 30;echo world', in the context of a canary deployment operation involving nginx instances. Configure the job to run 5 times, one after the other. After completion, verify the job's status and then delete it.

<details><summary>show</summary>
<p>

```bash
kubectl create job busybox --image=busybox --dry-run=client -o yaml -- /bin/sh -c 'echo hello;sleep 30;echo world' > job.yaml
vi job.yaml
```

Add job.spec.completions=5

```YAML
apiVersion: batch/v1
kind: Job
metadata:
  creationTimestamp: null
  labels:
    run: busybox
  name: busybox
spec:
  completions: 5 # add this line
  template:
    metadata:
      creationTimestamp: null
      labels:
        run: busybox
    spec:
      containers:
      - args:
        - /bin/sh
        - -c
        - echo hello;sleep 30;echo world
        image: busybox
        name: busybox
        resources: {}
      restartPolicy: OnFailure
status: {}
```

```bash
kubectl create -f job.yaml
```

Verify that it has been completed:

```bash
kubectl get job busybox -w # will take two and a half minutes
kubectl delete jobs busybox
```

</p>
</details>

### Create a job in Kubernetes that uses the image busybox with the command 'echo hello;sleep 30;echo world', in the context of a canary deployment operation involving nginx instances. This time, configure the job to run 5 parallel instances. After completion, verify the job's status and then delete it.

<details><summary>show</summary>
<p>

```bash
vi job.yaml
```

Add job.spec.parallelism=5

```YAML
apiVersion: batch/v1
kind: Job
metadata:
  creationTimestamp: null
  labels:
    run: busybox
  name: busybox
spec:
  parallelism: 5 # add this line
  template:
    metadata:
      creationTimestamp: null
      labels:
        run: busybox
    spec:
      containers:
      - args:
        - /bin/sh
        - -c
        - echo hello;sleep 30;echo world
        image: busybox
        name: busybox
        resources: {}
      restartPolicy: OnFailure
status: {}
```

```bash
kubectl create -f job.yaml
kubectl get jobs
```

It will take some time for the parallel jobs to finish (>= 30 seconds)

```bash
kubectl delete job busybox
```

</p>
</details>

### Create a job in Kubernetes using the image busybox with the command 'echo hello; sleep 30; echo world', similar to the context of a canary deployment operation involving nginx instances, but this time ensure that it will be automatically terminated by Kubernetes if it takes more than 30 seconds to execute. Configure the job to run 5 parallel instances as before.

<details><summary>show</summary>
<p>

```bash
kubectl create job busybox --image=busybox --dry-run=client -o yaml -- /bin/sh -c 'while true; do echo hello; sleep 10;done' > job.yaml
vi job.yaml
```

Add job.spec.activeDeadlineSeconds=30

```bash
apiVersion: batch/v1
kind: Job
metadata:
  creationTimestamp: null
  labels:
    run: busybox
  name: busybox
spec:
  activeDeadlineSeconds: 30 # add this line
  template:
    metadata:
      creationTimestamp: null
      labels:
        run: busybox
    spec:
      containers:
      - args:
        - /bin/sh
        - -c
        - while true; do echo hello; sleep 10;done
        image: busybox
        name: busybox
        resources: {}
      restartPolicy: OnFailure
status: {}
```
</p>
</details>

## Cron jobs

kubernetes.io > Documentation > Tasks > Run Jobs > [Running Automated Tasks with a CronJob](https://kubernetes.io/docs/tasks/job/automated-tasks-with-cron-jobs/)

### Create a cron job in Kubernetes using the image busybox that runs on a schedule of "*/1 * * * *" and writes 'date; echo Hello from the Kubernetes cluster' to standard output, following the context of configuring Kubernetes jobs to perform specific tasks, similar to how you configured a job with parallel instances and automatic termination.

<details><summary>show</summary>
<p>

```bash
kubectl create cronjob busybox --image=busybox --schedule="*/1 * * * *" -- /bin/sh -c 'date; echo Hello from the Kubernetes cluster'
```

</p>
</details>

### View the logs of the cron job you created in Kubernetes with the busybox image, running on a schedule of "*/1 * * * *" and writing 'date; echo Hello from the Kubernetes cluster' to standard output, and then delete it.

<details><summary>show</summary>
<p>

```bash
kubectl get po # copy the ID of the pod whose container was just created
kubectl logs <busybox-***> # you will see the date and message 
kubectl delete cj busybox # cj stands for cronjob
```

</p>
</details>

### Create a cron job in Kubernetes using the busybox image, with the schedule "*/1 * * * *", that writes 'date; echo Hello from the Kubernetes cluster' to standard output. Watch the cron job's status until it runs. After it has run, check which job was executed by this cron job, view its log, and then delete the cron job.

<details><summary>show</summary>
<p>

```bash
kubectl get cj
kubectl get jobs --watch
kubectl get po --show-labels # observe that the pods have a label that mentions their 'parent' job
kubectl logs busybox-1529745840-m867r
# Bear in mind that Kubernetes will run a new job/pod for each new cron job
kubectl delete cj busybox
```

</p>
</details>

### Create a cron job in Kubernetes using the busybox image, with the schedule "*/1 * * * *" (which means it runs every minute), that writes 'date; echo Hello from the Kubernetes cluster' to standard output. Ensure the cron job is configured to be terminated if it takes more than 17 seconds to start execution after its scheduled time, indicating that the job has missed its scheduled time to run.

<details><summary>show</summary>
<p>

```bash
kubectl create cronjob time-limited-job --image=busybox --restart=Never --dry-run=client --schedule="* * * * *" -o yaml -- /bin/sh -c 'date; echo Hello from the Kubernetes cluster' > time-limited-job.yaml
vi time-limited-job.yaml
```
Add cronjob.spec.startingDeadlineSeconds=17

```bash
apiVersion: batch/v1
kind: CronJob
metadata:
  creationTimestamp: null
  name: time-limited-job
spec:
  startingDeadlineSeconds: 17 # add this line
  jobTemplate:
    metadata:
      creationTimestamp: null
      name: time-limited-job
    spec:
      template:
        metadata:
          creationTimestamp: null
        spec:
          containers:
          - args:
            - /bin/sh
            - -c
            - date; echo Hello from the Kubernetes cluster
            image: busybox
            name: time-limited-job
            resources: {}
          restartPolicy: Never
  schedule: '* * * * *'
status: {}
```

</p>
</details>

### Create a cron job in Kubernetes using the busybox image, with the schedule "*/1 * * * *" (which means it runs every minute), that writes 'date; echo Hello from the Kubernetes cluster' to standard output. This cron job should not only be configured to be terminated if it takes more than 17 seconds to start execution after its scheduled time but should also be terminated if it successfully starts and takes more than 12 seconds to complete execution.

<details><summary>show</summary>
<p>

```bash
kubectl create cronjob time-limited-job --image=busybox --restart=Never --dry-run=client --schedule="* * * * *" -o yaml -- /bin/sh -c 'date; echo Hello from the Kubernetes cluster' > time-limited-job.yaml
vi time-limited-job.yaml
```
Add cronjob.spec.jobTemplate.spec.activeDeadlineSeconds=12

```bash
apiVersion: batch/v1
kind: CronJob
metadata:
  creationTimestamp: null
  name: time-limited-job
spec:
  jobTemplate:
    metadata:
      creationTimestamp: null
      name: time-limited-job
    spec:
      activeDeadlineSeconds: 12 # add this line
      template:
        metadata:
          creationTimestamp: null
        spec:
          containers:
          - args:
            - /bin/sh
            - -c
            - date; echo Hello from the Kubernetes cluster
            image: busybox
            name: time-limited-job
            resources: {}
          restartPolicy: Never
  schedule: '* * * * *'
status: {}
```

</p>
</details>

### Create a Kubernetes job based on a cron job that uses the busybox image, with the schedule "*/1 * * * *" (which means it runs every minute), to write 'date; echo Hello from the Kubernetes cluster' to standard output. This cron job is configured to be terminated if it takes more than 17 seconds to start execution after its scheduled time and also terminated if it successfully starts but takes more than 12 seconds to complete execution.

<details><summary>show</summary>
<p>

```bash
kubectl create job --from=cronjob/sample-cron-job sample-job
```
</p>
</details>
