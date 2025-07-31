![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/state&empty)
# State Persistence (8%)

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Configure a Pod to Use a Volume for Storage](https://kubernetes.io/docs/tasks/configure-pod-container/configure-volume-storage/)

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Configure a Pod to Use a PersistentVolume for Storage](https://kubernetes.io/docs/tasks/configure-pod-container/configure-persistent-volume-storage/)

## Define volumes 

### Create busybox pod with two containers, each one will have the image busybox and will run the 'sleep 3600' command. Make both containers mount an emptyDir at '/etc/foo'. Connect to the second busybox, write the first column of '/etc/passwd' file to '/etc/foo/passwd'. Connect to the first busybox and write '/etc/foo/passwd' file to standard output. Delete pod.

<details><summary>show</summary>
<p>

*This question is probably a better fit for the 'Multi-container-pods' section but I'm keeping it here as it will help you get acquainted with state*

The easiest way to do this is to create a template pod with:

```bash
kubectl run busybox --image=busybox --restart=Never -o yaml --dry-run=client -- /bin/sh -c 'sleep 3600' > pod.yaml
vi pod.yaml
```
Copy paste the container definition and type the lines that have a comment in the end:

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: busybox
  name: busybox
spec:
  dnsPolicy: ClusterFirst
  restartPolicy: Never
  containers:
  - args:
    - /bin/sh
    - -c
    - sleep 3600
    image: busybox
    imagePullPolicy: IfNotPresent
    name: busybox
    resources: {}
    volumeMounts: #
    - name: myvolume #
      mountPath: /etc/foo #
  - args:
    - /bin/sh
    - -c
    - sleep 3600
    image: busybox
    name: busybox2 # don't forget to change the name during copy paste, must be different from the first container's name!
    volumeMounts: #
    - name: myvolume #
      mountPath: /etc/foo #
  volumes: #
  - name: myvolume #
    emptyDir: {} #
```
In case you forget to add ```bash -- /bin/sh -c 'sleep 3600'``` in template pod create command, you can include command field in config file

```YAML
spec:
  containers:
  - image: busybox
    name: busybox
    command: ["/bin/sh", "-c", "sleep 3600"]
```

Connect to the second container:

```bash
kubectl exec -it busybox -c busybox2 -- /bin/sh
cat /etc/passwd | cut -f 1 -d ':' > /etc/foo/passwd # instead of cut command you can use awk -F ":" '{print $1}'
cat /etc/foo/passwd # confirm that stuff has been written successfully
exit
```

Connect to the first container:

```bash
kubectl exec -it busybox -c busybox -- /bin/sh
mount | grep foo # confirm the mounting
cat /etc/foo/passwd
exit
kubectl delete po busybox
```

</p>
</details>


### Create a PersistentVolume named 'myvolume' with a size of 10Gi, supporting access modes 'ReadWriteOnce' and 'ReadWriteMany', and using the storageClassName 'normal'. This PersistentVolume should be configured to mount on hostPath '/etc/foo', replicating the setup from a previous task where a busybox pod with two containers was created to share an emptyDir volume at '/etc/foo'. Write the PersistentVolume configuration to a file named pv.yaml and apply it to your Kubernetes cluster. Afterward, display the list of PersistentVolumes currently available in the cluster.

<details><summary>show</summary>
<p>

```bash
vi pv.yaml
```

```YAML
kind: PersistentVolume
apiVersion: v1
metadata:
  name: myvolume
spec:
  storageClassName: normal
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
    - ReadWriteMany
  hostPath:
    path: /etc/foo
```

Show the PersistentVolumes:

```bash
kubectl create -f pv.yaml
# will have status 'Available'
kubectl get pv
```

</p>
</details>

### Create a PersistentVolumeClaim named 'mypvc' to use with the existing PersistentVolume 'myvolume'. The 'myvolume' PersistentVolume was previously created with a size of 10Gi, supports access modes 'ReadWriteOnce' and 'ReadWriteMany', and uses the storageClassName 'normal'. Configure 'mypvc' with a request for 4Gi, an access mode of ReadWriteOnce, and the same storageClassName 'normal'. Write the PersistentVolumeClaim configuration to a file named pvc.yaml and apply it to your Kubernetes cluster. Afterward, display the list of PersistentVolumeClaims and the list of PersistentVolumes currently available in the cluster.

<details><summary>show</summary>
<p>

```bash
vi pvc.yaml
```

```YAML
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: mypvc
spec:
  storageClassName: normal
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 4Gi
```

Create it on the cluster:

```bash
kubectl create -f pvc.yaml
```

Show the PersistentVolumeClaims and PersistentVolumes:

```bash
kubectl get pvc # will show as 'Bound'
kubectl get pv # will show as 'Bound' as well
```

</p>
</details>

### Create a busybox pod with the command 'sleep 3600' and save the configuration to a file named pod.yaml. Mount the PersistentVolumeClaim 'mypvc', which was configured with a request for 4Gi, an access mode of ReadWriteOnce, and with the storageClassName 'normal', to the directory '/etc/foo' within the pod. After the pod is running, connect to the 'busybox' pod and copy the '/etc/passwd' file to '/etc/foo/passwd'.

<details><summary>show</summary>
<p>

Create a skeleton pod:

```bash
kubectl run busybox --image=busybox --restart=Never -o yaml --dry-run=client -- /bin/sh -c 'sleep 3600' > pod.yaml
vi pod.yaml
```

Add the lines that finish with a comment:

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
  - args:
    - /bin/sh
    - -c
    - sleep 3600
    image: busybox
    imagePullPolicy: IfNotPresent
    name: busybox
    resources: {}
    volumeMounts: #
    - name: myvolume #
      mountPath: /etc/foo #
  dnsPolicy: ClusterFirst
  restartPolicy: Never
  volumes: #
  - name: myvolume #
    persistentVolumeClaim: #
      claimName: mypvc #
status: {}
```

Create the pod:

```bash
kubectl create -f pod.yaml
```

Connect to the pod and copy '/etc/passwd' to '/etc/foo/passwd':

```bash
kubectl exec busybox -it -- cp /etc/passwd /etc/foo/passwd
```

</p>
</details>

### Create a second busybox pod with the command 'sleep 3600,' ensuring it mounts the PersistentVolumeClaim 'mypvc'—which is configured with a request for 4Gi, an access mode of ReadWriteOnce, and with the storageClassName 'normal'—to the directory '/etc/foo,' similarly to the first pod you created as described. Save the configuration to a file with a different name, ensuring you change only the 'name' property of the pod in your YAML file. After the pod is running, connect to this new busybox pod and verify that '/etc/foo' contains the 'passwd' file, which was previously copied to this location in the first pod. Delete both pods to clean up after the verification. If you cannot see the 'passwd' file from the second pod, identify the reason why it might not be visible and propose a solution to fix this issue.



<details><summary>show</summary>
<p>

Create the second pod, called busybox2:

```bash
vim pod.yaml
# change 'metadata.name: busybox' to 'metadata.name: busybox2'
kubectl create -f pod.yaml
kubectl exec busybox2 -- ls /etc/foo # will show 'passwd'
# cleanup
kubectl delete po busybox busybox2
kubectl delete pvc mypvc
kubectl delete pv myvolume
```

If the file doesn't show on the second pod but it shows on the first, it has most likely been scheduled on a different node.

```bash
# check which nodes the pods are on
kubectl get po busybox -o wide
kubectl get po busybox2 -o wide
```

If they are on different nodes, you won't see the file, because we used the `hostPath` volume type.
If you need to access the same files in a multi-node cluster, you need a volume type that is independent of a specific node.
There are lots of different types per cloud provider [(see here)](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#types-of-persistent-volumes), a general solution could be to use NFS.

</p>
</details>

### Create a busybox pod with the command 'sleep 3600,' ensuring it mounts the same PersistentVolumeClaim 'mypvc'—configured with a request for 4Gi, an access mode of ReadWriteOnce, and with the storageClassName 'normal'—to the directory '/etc/foo'. After the pod is running, copy '/etc/passwd' to '/etc/foo' within the pod, and then copy '/etc/foo/passwd' from the pod to your local folder.

<details><summary>show</summary>
<p>

```bash
kubectl run busybox --image=busybox --restart=Never -- sleep 3600
kubectl cp busybox:/etc/passwd ./passwd # kubectl cp command
# previous command might report an error, feel free to ignore it since copy command works
cat passwd
```

</p>
</details>
