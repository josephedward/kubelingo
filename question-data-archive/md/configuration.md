![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/configuration&empty)
# Configuration (18%)

[ConfigMaps](#configmaps)

[SecurityContext](#securitycontext)

[Requests and Limits](#requests-and-limits)

[Secrets](#secrets)

[Service Accounts](#serviceaccounts)

<br>#Tips, export to variable<br>
<br>export ns="-n secret-ops"</br>
<br>export do="--dry-run=client -oyaml"</br>
## ConfigMaps

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Configure a Pod to Use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)

### Create a configmap named config with values foo=lala,foo2=lolo

<details><summary>show</summary>
<p>

```bash
kubectl create configmap config --from-literal=foo=lala --from-literal=foo2=lolo
```

</p>
</details>

### Display the values of the configmap named config with values foo=lala,foo2=lolo.

<details><summary>show</summary>
<p>

```bash
kubectl get cm config -o yaml
# or
kubectl describe cm config
```

</p>
</details>

### Create and display a configmap from a file, following the example where the values of a configmap named config with values foo=lala,foo2=lolo were displayed.

Create the file with

```bash
echo -e "foo3=lili\nfoo4=lele" > config.txt
```

<details><summary>show</summary>
<p>

```bash
kubectl create cm configmap2 --from-file=config.txt
kubectl get cm configmap2 -o yaml
```

</p>
</details>

### Create and display a configmap from a .env file, similar to the previous exercise where a configmap named config with values foo=lala,foo2=lolo was created and displayed.

Create the file with the command

```bash
echo -e "var1=val1\n# this is a comment\n\nvar2=val2\n#anothercomment" > config.env
```

<details><summary>show</summary>
<p>

```bash
kubectl create cm configmap3 --from-env-file=config.env
kubectl get cm configmap3 -o yaml
```

</p>
</details>

### Create and display a configmap from a file, similar to the previous exercise where a configmap named config with values foo=lala,foo2=lolo was created and displayed, giving the key 'special'.

Create the file with

```bash
echo -e "var3=val3\nvar4=val4" > config4.txt
```

<details><summary>show</summary>
<p>

```bash
kubectl create cm configmap4 --from-file=special=config4.txt
kubectl describe cm configmap4
kubectl get cm configmap4 -o yaml
```

</p>
</details>

### Create a configMap named 'options' with the value var5=val5, similar to the exercise where a configmap named config with values foo=lala,foo2=lolo was created. Then, create a new nginx pod that loads the value from variable 'var5' into an environment variable named 'option'.

<details><summary>show</summary>
<p>

```bash
kubectl create cm options --from-literal=var5=val5
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
    env:
    - name: option # name of the env variable
      valueFrom:
        configMapKeyRef:
          name: options # name of config map
          key: var5 # name of the entity in config map
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl exec -it nginx -- env | grep option # will show 'option=val5'
```

</p>
</details>

### Create a configMap named 'anotherone' with the values 'var6=val6' and 'var7=val7', similar to the previous task where you created a configMap named 'options' with the value 'var5=val5'. Then, create a new nginx pod that loads the values from 'var6' and 'var7' into environment variables, resembling the method used to load 'var5' into the 'option' environment variable in the nginx pod you previously set up.

<details><summary>show</summary>
<p>

```bash
kubectl create configmap anotherone --from-literal=var6=val6 --from-literal=var7=val7
kubectl run --restart=Never nginx --image=nginx -o yaml --dry-run=client > pod.yaml
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
    envFrom: # different than previous one, that was 'env'
    - configMapRef: # different from the previous one, was 'configMapKeyRef'
        name: anotherone # the name of the config map
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl exec -it nginx -- env 
```

</p>
</details>

### Create a configMap named 'cmvolume' with the values 'var8=val8' and 'var9=val9'. Then create a new nginx pod that loads this configMap as a volume, similarly to how you created a new nginx pod that loaded values from a configMap into environment variables in a previous task. Mount the 'cmvolume' configMap at the path '/etc/lala' inside the nginx pod. After the pod is running, use the 'ls' command to list the contents of the '/etc/lala' directory to verify the configMap's values were correctly loaded.

<details><summary>show</summary>
<p>

```bash
kubectl create configmap cmvolume --from-literal=var8=val8 --from-literal=var9=val9
kubectl run nginx --image=nginx --restart=Never -o yaml --dry-run=client > pod.yaml
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
  volumes: # add a volumes list
  - name: myvolume # just a name, you'll reference this in the pods
    configMap:
      name: cmvolume # name of your configmap
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
    volumeMounts: # your volume mounts are listed here
    - name: myvolume # the name that you specified in pod.spec.volumes.name
      mountPath: /etc/lala # the path inside your container
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl exec -it nginx -- /bin/sh
cd /etc/lala
ls # will show var8 var9
cat var8 # will show val8
```

</p>
</details>

## SecurityContext

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)

### Create the YAML for an nginx pod that runs with the user ID 101, ensuring it follows the practice of loading a configMap named 'cmvolume' with the values 'var8=val8' and 'var9=val9' as a volume. The configMap should be mounted at the path '/etc/lala' inside the nginx pod as demonstrated in a related task. No need to create the pod.

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
  securityContext: # insert this line
    runAsUser: 101 # UID for the user
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

</p>
</details>


### Create the YAML for an nginx pod that runs with the user ID 101, ensures it follows the practice of loading a configMap named 'cmvolume' with the values 'var8=val8' and 'var9=val9' as a volume, which should be mounted at the path '/etc/lala' inside the nginx pod, and has the capabilities "NET_ADMIN", "SYS_TIME" added to its single container.

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
    securityContext: # insert this line
      capabilities: # and this
        add: ["NET_ADMIN", "SYS_TIME"] # this as well
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

</p>
</details>

## Resource requests and limits

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Assign CPU Resources to Containers and Pods](https://kubernetes.io/docs/tasks/configure-pod-container/assign-cpu-resource/)

### Create the YAML for an nginx pod that runs with the user ID 101, ensures it loads a configMap named 'cmvolume' with the values 'var8=val8' and 'var9=val9' as a volume mounted at '/etc/lala', has the capabilities "NET_ADMIN", "SYS_TIME" in its single container, and specifies resource requests of cpu=100m, memory=256Mi along with limits of cpu=200m, memory=512Mi.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --dry-run=client -o yaml > pod.yaml
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
    name: nginx
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:    
        memory: "512Mi"
        cpu: "200m"
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
``` 

</p>
</details>

## Limit Ranges
kubernetes.io > Documentation > Concepts > Policies > Limit Ranges (https://kubernetes.io/docs/concepts/policy/limit-range/)

### Create a namespace named limitrange and within it, define a LimitRange that sets the maximum memory limit for pods at 500Mi and the minimum at 100Mi, ensuring it accommodates the specifications of a pod like the nginx pod from the previous context which includes resource requests and limits.

<details><summary>show</summary>
<p>

```bash
kubectl create ns limitrange
```

vi 1.yaml
```YAML
apiVersion: v1
kind: LimitRange
metadata:
  name: ns-memory-limit
  namespace: limitrange
spec:
  limits:
  - max: # max and min define the limit range
      memory: "500Mi"
    min:
      memory: "100Mi"
    type: Pod
```

```bash
kubectl apply -f 1.yaml
```
</p>
</details>

### Describe the characteristics and purpose of the namespace named limitrange where you have defined a LimitRange setting the maximum memory limit for pods at 500Mi and the minimum at 100Mi.

<details><summary>show</summary>
<p>

```bash
kubectl describe limitrange ns-memory-limit -n limitrange
```
</p>
</details>

### Create an nginx pod that requests 250Mi of memory in the namespace named limitrange, where a LimitRange has been defined setting the maximum memory limit for pods at 500Mi and the minimum at 100Mi.

<details><summary>show</summary>
<p>

vi 2.yaml
```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
  namespace: limitrange
spec:
  containers:
  - image: nginx
    name: nginx
    resources:
      requests:
        memory: "250Mi"
      limits:
        memory: "500Mi" # limit has to be specified and be <= limitrange
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
``` 

```bash
kubectl apply -f 2.yaml
```
</p>
</details>


## Resource Quotas
kubernetes.io > Documentation > Concepts > Policies > Resource Quotas (https://kubernetes.io/docs/concepts/policy/resource-quotas/)

### Create a ResourceQuota in the namespace `one` specifying hard requests for `cpu=1` and `memory=1Gi`, and hard limits for `cpu=2` and `memory=2Gi`. This is in the context of managing Kubernetes resources where, previously, you were asked to create an nginx pod requesting 250Mi of memory in a namespace called limitrange, which had a LimitRange set with a maximum memory limit of 500Mi for pods and a minimum of 100Mi.

<details><summary>show</summary>
<p>

Create the namespace:
```bash
kubectl create ns one
```

Create the ResourceQuota
```bash
vi rq-one.yaml
```

```YAML
apiVersion: v1
kind: ResourceQuota
metadata:
  name: my-rq
  namespace: one
spec:
  hard:
    requests.cpu: "1"
    requests.memory: 1Gi
    limits.cpu: "2"
    limits.memory: 2Gi
```

```bash
kubectl apply -f rq-one.yaml
```

or
```bash
kubectl create quota my-rq --namespace=one --hard=requests.cpu=1,requests.memory=1Gi,limits.cpu=2,limits.memory=2Gi
```
</p>
</details>

### After having created a ResourceQuota in the namespace `one` specifying hard requests for `cpu=1` and `memory=1Gi`, as well as hard limits for `cpu=2` and `memory=2Gi`, attempt to create a pod within the same namespace with resource requests `cpu=2`, `memory=3Gi` and limits `cpu=3`, `memory=4Gi`.

<details><summary>show</summary>
<p>

```bash
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
  namespace: one
spec:
  containers:
  - image: nginx
    name: nginx
    resources:
      requests:
        memory: "3Gi"
        cpu: "2"
      limits:
        memory: "4Gi"
        cpu: "3"
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
```

```bash
kubectl create -f pod.yaml
```

Expected error message:
```bash
Error from server (Forbidden): error when creating "pod.yaml": pods "nginx" is forbidden: exceeded quota: my-rq, requested: limits.cpu=3,limits.memory=4Gi,requests.cpu=2,requests.memory=3Gi, used: limits.cpu=0,limits.memory=0,requests.cpu=0,requests.memory=0, limited: limits.cpu=2,limits.memory=2Gi,requests.cpu=1,requests.memory=1Gi
```
</p>
</details>

### Given a ResourceQuota in namespace `one` specifying hard requests for `cpu=1` and `memory=1Gi`, as well as hard limits for `cpu=2` and `memory=2Gi`, create a pod within the same namespace with resource requests `cpu=0.5`, `memory=1Gi` and limits `cpu=1`, `memory=2Gi`.

<details><summary>show</summary>
<p>

```bash
vi pod2.yaml
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
  namespace: one
spec:
  containers:
  - image: nginx
    name: nginx
    resources:
      requests:
        memory: "1Gi"
        cpu: "0.5"
      limits:
        memory: "2Gi"
        cpu: "1"
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
```

```bash
kubectl create -f pod2.yaml
```

Show the ResourceQuota usage in namespace `one`
```bash
kubectl get resourcequota -n one
```

```
NAME    AGE   REQUEST                                          LIMIT
my-rq   10m   requests.cpu: 500m/1, requests.memory: 1Gi/1Gi   limits.cpu: 1/2, limits.memory: 2Gi/2Gi
```
</p>
</details>


## Secrets

kubernetes.io > Documentation > Concepts > Configuration > [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)

kubernetes.io > Documentation > Tasks > Inject Data Into Applications > [Distribute Credentials Securely Using Secrets](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/)

### Create a secret called mysecret with the values password=mypass in the namespace 'one'.

<details><summary>show</summary>
<p>

```bash
kubectl create secret generic mysecret --from-literal=password=mypass
```

</p>
</details>

### Create a secret called mysecret2 in the same Kubernetes namespace as the previous secret ('one') that gets key/value pairs from a file.

Create a file called username with the value admin:

```bash
echo -n admin > username
```

<details><summary>show</summary>
<p>

```bash
kubectl create secret generic mysecret2 --from-file=username
```

</p>
</details>

### Retrieve the value of the secret named 'mysecret2', which was created in the same Kubernetes namespace as the secret named 'one', using key/value pairs sourced from a file.

<details><summary>show</summary>
<p>

```bash
kubectl get secret mysecret2 -o yaml
echo -n YWRtaW4= | base64 -d # on MAC it is -D, which decodes the value and shows 'admin'
```

Alternative using `--jsonpath`:

```bash
kubectl get secret mysecret2 -o jsonpath='{.data.username}' | base64 -d  # on MAC it is -D
```

Alternative using `--template`:

```bash
kubectl get secret mysecret2 --template '{{.data.username}}' | base64 -d  # on MAC it is -D
```

Alternative using `jq`:

```bash
kubectl get secret mysecret2 -o json | jq -r .data.username | base64 -d  # on MAC it is -D
```

</p>
</details>

### Create an nginx pod that mounts the secret named 'mysecret2', which was created in the same Kubernetes namespace as the secret named 'one' using key/value pairs sourced from a file, in a volume on path /etc/foo.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --restart=Never -o yaml --dry-run=client > pod.yaml
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
  volumes: # specify the volumes
  - name: foo # this name will be used for reference inside the container
    secret: # we want a secret
      secretName: mysecret2 # name of the secret - this must already exist on pod creation
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
    volumeMounts: # our volume mounts
    - name: foo # name on pod.spec.volumes
      mountPath: /etc/foo #our mount path
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl exec -it nginx -- /bin/bash
ls /etc/foo  # shows username
cat /etc/foo/username # shows admin
```

</p>
</details>

### Delete the nginx pod that mounts the secret named 'mysecret2', previously created in the same Kubernetes namespace as the secret named 'one' using key/value pairs sourced from a file, in a volume on path /etc/foo. Then, mount the variable 'username' from secret 'mysecret2' onto a new nginx pod in an environment variable called 'USERNAME'.

<details><summary>show</summary>
<p>

```bash
kubectl delete po nginx
kubectl run nginx --image=nginx --restart=Never -o yaml --dry-run=client > pod.yaml
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
    env: # our env variables
    - name: USERNAME # asked name
      valueFrom:
        secretKeyRef: # secret reference
          name: mysecret2 # our secret's name
          key: username # the key of the data in the secret
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

```bash
kubectl create -f pod.yaml
kubectl exec -it nginx -- env | grep USERNAME | cut -d '=' -f 2 # will show 'admin'
```

</p>
</details>

### Create a Secret named 'ext-service-secret' in the namespace 'secret-ops', separate from the namespace involving 'mysecret2' and the nginx pod operation. Then, provide the key-value pair API_KEY=LmLHbYhsgWZwNifiqaRorH8T as a literal to the secret.

<details><summary>show</summary>
<p>

```bash
export ns="-n secret-ops"
export do="--dry-run=client -oyaml"
k create secret generic ext-service-secret --from-literal=API_KEY=LmLHbYhsgWZwNifiqaRorH8T $ns $do > sc.yaml
k apply -f sc.yaml
```

</p>
</details>

### Create a Pod named 'consumer' with the image 'nginx' in the namespace 'secret-ops' where you have previously created a Secret named 'ext-service-secret' containing the key-value pair API_KEY=LmLHbYhsgWZwNifiqaRorH8T. Ensure this Secret is consumed as an environment variable by the Pod. Then, open an interactive shell to the Pod, and print all environment variables to confirm the Secret's consumption.
<details><summary>show</summary>
<p>

```bash
export ns="-n secret-ops"
export do="--dry-run=client -oyaml"
k run consumer --image=nginx $ns $do > nginx.yaml
vi nginx.yaml
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: consumer
  name: consumer
  namespace: secret-ops
spec:
  containers:
  - image: nginx
    name: consumer
    resources: {}
    env:
    - name: API_KEY
      valueFrom:
        secretKeyRef:
          name: ext-service-secret
          key: API_KEY
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
```

```bash
k exec -it $ns consumer -- /bin/sh
#env
```
</p>
</details>

### After successfully creating a Pod named 'consumer' with the image 'nginx' in the namespace 'secret-ops', where you created a Secret named 'ext-service-secret' containing the key-value pair API_KEY=LmLHbYhsgWZwNifiqaRorH8T and ensured this Secret is consumed as an environment variable by the Pod, proceed to create a new Secret named 'my-secret' of type 'kubernetes.io/ssh-auth' in the same namespace 'secret-ops'. For this new Secret, define a single key named 'ssh-privatekey', and ensure it is pointing to the file 'id_rsa' found in this directory.
<details><summary>show</summary>
<p>

```bash
#Tips, export to variable
export do="--dry-run=client -oyaml"
export ns="-n secret-ops"

#if id_rsa file didn't exist.
ssh-keygen

k create secret generic my-secret $ns --type="kubernetes.io/ssh-auth" --from-file=ssh-privatekey=id_rsa $do > sc.yaml
k apply -f sc.yaml
```
</p>
</details>

### Create a Pod named 'consumer' with the image 'nginx' in the namespace 'secret-ops', and consume the newly created 'my-secret' Secret, which is of type 'kubernetes.io/ssh-auth' containing a key 'ssh-privatekey' that points to the file 'id_rsa', as a Volume. Mount this Secret as a Volume to the path /var/app with read-only access. Open an interactive shell to the Pod, and render the contents of the file.
<details><summary>show</summary>
<p>

```bash
#Tips, export to variable
export ns="-n secret-ops"
export do="--dry-run=client -oyaml"
k run consumer --image=nginx $ns $do > nginx.yaml
vi nginx.yaml
```

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: consumer
  name: consumer
  namespace: secret-ops
spec:
  containers:
    - image: nginx
      name: consumer
      resources: {}
      volumeMounts:
        - name: foo
          mountPath: "/var/app"
          readOnly: true
  volumes:
    - name: foo
      secret:
        secretName: my-secret
        optional: true
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
```

```bash
k exec -it $ns consumer -- /bin/sh
# cat /var/app/ssh-privatekey
# exit
```
</p>
</details>

## ServiceAccounts

kubernetes.io > Documentation > Tasks > Configure Pods and Containers > [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)

### List all the service accounts in a Kubernetes cluster across all namespaces.

<details><summary>show</summary>
<p>

```bash
kubectl get sa --all-namespaces
```
Alternatively 

```bash
kubectl get sa -A
```

</p>
</details>

### Create a new service account called 'myuser' in a Kubernetes cluster.

<details><summary>show</summary>
<p>

```bash
kubectl create sa myuser
```

Alternatively:

```bash
# let's get a template easily
kubectl get sa default -o yaml > sa.yaml
vim sa.yaml
```

```YAML
apiVersion: v1
kind: ServiceAccount
metadata:
  name: myuser
```

```bash
kubectl create -f sa.yaml
```

</p>
</details>

### Create an nginx pod that uses a service account called 'myuser' in a Kubernetes cluster.

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --restart=Never -o yaml --dry-run=client > pod.yaml
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
  serviceAccountName: myuser # we use pod.spec.serviceAccountName
  containers:
  - image: nginx
    imagePullPolicy: IfNotPresent
    name: nginx
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Never
status: {}
```

or

```YAML
apiVersion: v1
kind: Pod
metadata:
  creationTimestamp: null
  labels:
    run: nginx
  name: nginx
spec:
  serviceAccount: myuser # we use pod.spec.serviceAccount
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
kubectl get pod nginx -o jsonpath='{.spec.serviceAccountName}' # output: myuser

kubectl exec -it nginx -- cat /var/run/secrets/kubernetes.io/serviceaccount/token # to check if the ServiceAccount token is mounted inside the Pod. Starting from Kubernetes 1.24+, the token is dynamically projected into the Pod

```

</p>
</details>

### Generate an API token for the service account 'myuser' used by an nginx pod in a Kubernetes cluster.

<details><summary>show</summary>
<p>
  
```bash
kubectl create token myuser
```

</p>
</details>
