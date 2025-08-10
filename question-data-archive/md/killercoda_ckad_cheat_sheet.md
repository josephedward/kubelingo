 # Killercoda CKAD Quiz – Quick Reference

 This cheat sheet breaks each Killercoda CKAD scenario into clear, numbered steps with exact commands or manifests. No multi-resource Vim juggling—each action is standalone.

 ---

 ## 1) Namespaces & Pod with Resource Limits

 **Original prompt:**
 > Create a new Namespace `limit`.
 > In that Namespace create a Pod named `resource-checker` of image `httpd:alpine`.
 > The container should be named `my-container`.
 > It should request `30m` CPU and be limited to `300m` CPU.
 > It should request `30Mi` memory and be limited to `30Mi` memory.

 ### Steps
 1. Create the `limit` Namespace
    ```bash
    kubectl create namespace limit
    ```
 2. Save the Pod manifest (`pod.yaml`):
    ```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: resource-checker
      namespace: limit
    spec:
      containers:
      - name: my-container
        image: httpd:alpine
        resources:
          requests:
            cpu:    "30m"
            memory: "30Mi"
          limits:
            cpu:    "300m"
            memory: "30Mi"
    ```
 3. Deploy the Pod
    ```bash
    kubectl apply -f pod.yaml
    ```

 ---

 ## 2) ConfigMaps

 **Original prompt:**
 > Create a ConfigMap named `trauerweide` with content `tree=trauerweide`.
 > Create the ConfigMap stored in existing file `/root/cm.yaml`.

 ### Steps
 1. Write the new ConfigMap manifest (`trauerweide.yaml`):
    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: trauerweide
    data:
      tree: trauerweide
    ```
 2. Apply both manifests
    ```bash
    kubectl apply -f trauerweide.yaml
    kubectl apply -f /root/cm.yaml
    ```

 ---

 ## 3) Pod with Env & Volume from ConfigMaps

 **Original prompt:**
 > Create a Pod named `pod1` of image `nginx:alpine`.
 > Make key `tree` of ConfigMap `trauerweide` available as environment variable `TREE1`.
 > Mount all keys of ConfigMap `birke` as a volume under `/etc/birke/*`.
 > Test env+volume access in the running Pod.

 ### Steps
 1. Write the Pod manifest (`pod1.yaml`):
    ```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: pod1
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        env:
        - name: TREE1
          valueFrom:
            configMapKeyRef:
              name: trauerweide
              key: tree
        volumeMounts:
        - name: birke-volume
          mountPath: /etc/birke
      volumes:
      - name: birke-volume
        configMap:
          name: birke
    ```
 2. Deploy the Pod
    ```bash
    kubectl apply -f pod1.yaml
    ```
 3. Verify inside the Pod
    ```bash
    kubectl exec -it pod1 -- /bin/sh
    echo $TREE1
    ls /etc/birke
    exit
    ```

 ---

 ## 4) Deployment with ReadinessProbe

 **Original prompt:**
 > Create a Deployment named `space-alien-welcome-message-generator` of image `httpd:alpine` with one replica.
 > It should have a ReadinessProbe which executes `stat /tmp/ready` (ready only after that file exists).
 > Use `initialDelaySeconds: 10`, `periodSeconds: 5`.
 > Create it and observe the Pod won’t become Ready.

 ### Steps
 1. Write the Deployment (`space-alien.yaml`):
    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: space-alien-welcome-message-generator
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: space-alien-welcome-message-generator
      template:
        metadata:
          labels:
            app: space-alien-welcome-message-generator
        spec:
          containers:
          - name: httpd
            image: httpd:alpine
            readinessProbe:
              exec:
                command: ["stat", "/tmp/ready"]
              initialDelaySeconds: 10
              periodSeconds: 5
    ```
 2. Apply and check Pod status
    ```bash
    kubectl apply -f space-alien.yaml
    kubectl get pods
    ```

 ---

 ## 5) Make the Deployment Ready

 **Original prompt:**
 > Exec into the Pod and create file `/tmp/ready`. Observe that the Pod becomes Ready.

 ### Steps
 1. Find the Pod and exec in
    ```bash
    POD=$(kubectl get pod -l app=space-alien-welcome-message-generator -o name)
    kubectl exec -it $POD -- /bin/sh
    ```
 2. Inside the container, create the file
    ```sh
    touch /tmp/ready
    exit
    ```
 3. Watch it turn Ready
    ```bash
    kubectl get pods
    ```

 ---

 ## 6) Rolling-Update Strategy Tweak

 **Original prompt:**
 > Application “wonderful” is running in default.
 > It’s on `httpd:alpine` but should switch to `nginx:alpine`.
 > Set `maxSurge: 50%`, `maxUnavailable: 0%`, then perform a rolling update.
 > Wait till rollout succeeds.

 ### Steps
 1. Patch the rollout strategy
    ```bash
    kubectl patch deployment wonderful \
      --type=json \
      -p='[{
        "op":"replace","path":"/spec/strategy/rollingUpdate/maxSurge","value":"50%"},
        {"op":"replace","path":"/spec/strategy/rollingUpdate/maxUnavailable","value":"0%"}
    ]'
    ```
 2. Update to the new image
    ```bash
    kubectl set image deployment/wonderful httpd=nginx:alpine
    ```
 3. Wait for rollout
    ```bash
    kubectl rollout status deployment/wonderful
    ```

 ---

 ## 7) Instant Cut-Over to v2

 **Original prompt:**
 > Switch instantly so all new requests hit `nginx:alpine`.
 > Create a new Deployment `wonderful-v2` (4 replicas, labels `app: wonderful`, `version: v2`).
 > Once v2 is Ready, retarget the Service, then scale v1 to 0.

 ### Steps
 1. Export v1 as base for v2
    ```bash
    kubectl get deployment wonderful-v1 -o yaml > wonderful-v2.yaml
    ```
 2. Edit `wonderful-v2.yaml`:
    - Change `metadata.name` to `wonderful-v2`
    - Set `spec.replicas` to `4`
    - Under both `spec.selector.matchLabels` and `spec.template.metadata.labels`, add:
      ```yaml
      version: v2
      ```
    - Change the container image to `nginx:alpine`
 3. Apply the new Deployment
    ```bash
    kubectl apply -f wonderful-v2.yaml
    ```
 4. Wait for all v2 Pods Ready
    ```bash
    kubectl rollout status deployment/wonderful-v2
    ```
 5. Retarget the Service to v2
    ```bash
    kubectl patch service wonderful \
      --type=json \
      -p='[{"op":"replace","path":"/spec/selector/version","value":"v2"}]'
    ```
 6. Scale down v1 to zero
    ```bash
    kubectl scale deployment wonderful-v1 --replicas=0
    ```

 ---

 ## 8) Canary-Style Rollout

 **Original prompt:**
 > Do a Canary: 20% new (`nginx:alpine`), 80% old.
 > Total Pods must be 10 across both Deployments.

 ### Steps
 1. Export base for the v2 canary
    ```bash
    kubectl get deployment wonderful-v1 -o yaml > wonderful-v2-canary.yaml
    ```
 2. Edit `wonderful-v2-canary.yaml`:
    - Change `metadata.name` to `wonderful-v2`
    - Set `spec.replicas` to `2`  # 20% of 10
    - Change the container image to `nginx:alpine`
 3. Apply the new canary Deployment
    ```bash
    kubectl apply -f wonderful-v2-canary.yaml
    ```
 4. Wait for v2 Pods Ready
    ```bash
    kubectl rollout status deployment/wonderful-v2
    ```
 5. Scale the old v1 to the remaining 80% (8 replicas)
    ```bash
    kubectl scale deployment wonderful-v1 --replicas=8
    ```

 ---

 ## 9) Install a Beta CRD & Object

 **Original prompt:**
 > Install the Shopping-Items CRD from `/code/crd.yaml`.
 > Then create a `ShoppingItem` named `bananas` in `default` with `dueDate=tomorrow` and `description=buy yellow ones`.

 ### Steps
 1. Install the CRD
    ```bash
    kubectl apply -f /code/crd.yaml
    ```
 2. Write the `ShoppingItem` manifest (`bananas.yaml`):
    ```yaml
    apiVersion: beta.killercoda.com/v1
    kind: ShoppingItem
    metadata:
      name: bananas
    spec:
      dueDate: tomorrow
      description: buy yellow ones
    ```
 3. Create the object
    ```bash
    kubectl apply -f bananas.yaml
    ```

 ---

 ## 10) Tear Down the CRD & Objects

 **Original prompt:**
 > Delete the CRD and all `ShoppingItem` objects.

 ### Steps
 1. Delete all ShoppingItems
    ```bash
    kubectl delete shoppingitem --all
    ```
 2. Delete the CRD
    ```bash
    kubectl delete crd shopping-items.beta.killercoda.com
    ```

 ---

 ## 11) Remove a Helm Release

 **Original prompt:**
 > Delete the Helm release `apiserver`.

 ### Steps
 1. List releases
    ```bash
    helm ls -A
    ```
 2. Uninstall `apiserver`
    ```bash
    helm delete apiserver -n team-yellow
    ```

 ---

 ## 12) Install a Helm Chart

 **Original prompt:**
 > Install the chart `falcosecurity/falco` into `team-yellow` as release `dev`.

 ### Steps
 1. (Optional) Add & update the repo
    ```bash
    helm repo add falcosecurity https://falcosecurity.github.io/charts
    helm repo update
    ```
 2. Install
    ```bash
    helm install dev falcosecurity/falco -n team-yellow
    ```

 ---

 ## 13) Expose Two Deployments as ClusterIP Services

 **Original prompt:**
 > There are two existing Deployments in Namespace `world` (`asia` & `europe`).
 > Create ClusterIP Services (port 80) named exactly after each Deployment.

 ### Steps
 1. Write `asia-svc.yaml`:
    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: asia
      namespace: world
    spec:
      selector:
        app: asia
      ports:
      - port: 80
        targetPort: 80
      type: ClusterIP
    ```
 2. Write `europe-svc.yaml` (similar, name: europe, selector: app: europe)
 3. Apply both
    ```bash
    kubectl apply -f asia-svc.yaml
    kubectl apply -f europe-svc.yaml
    ```

 ---

 ## 14) Configure an Ingress

 **Original prompt:**
 > Create an Ingress named `world` for host `world.universe.mine` with two routes: `/europe/` → Service `europe`, `/asia/` → Service `asia`.

 ### Steps
 1. (Optional) Verify the IngressController NodePort
    ```bash
    kubectl -n ingress-nginx get svc ingress-nginx-controller
    ```
 2. Write `world-ingress.yaml`:
    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: world
      namespace: world
    spec:
      ingressClassName: nginx
      rules:
      - host: world.universe.mine
        http:
          paths:
          - path: /europe/
            pathType: Prefix
            backend:
              service:
                name: europe
                port:
                  number: 80
          - path: /asia/
            pathType: Prefix
            backend:
              service:
                name: asia
                port:
                  number: 80
    ```
 3. Apply it
    ```bash
    kubectl apply -f world-ingress.yaml
    ```
 4. Test via `/etc/hosts` entry
    ```bash
    curl http://world.universe.mine:30080/europe/
    curl http://world.universe.mine:30080/asia/
    ```

---

## 15) Create a NetworkPolicy

**Original prompt:**
> There are existing Pods in Namespace `space1` and `space2`.
> We need a new NetworkPolicy named `np` that restricts all Pods in Namespace `space1`
> to only have outgoing traffic to Pods in Namespace `space2`. Incoming traffic not affected.
> The NetworkPolicy should still allow outgoing DNS traffic on port `53` TCP and UDP.

### Steps
1. Save this manifest as `np.yaml`:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: np
     namespace: space1
   spec:
     podSelector: {}
     policyTypes:
     - Egress
     egress:
     - to:
       - namespaceSelector:
           matchLabels:
             kubernetes.io/metadata.name: space2
       ports:
       - port: 53
         protocol: TCP
       - port: 53
         protocol: UDP
   ```
2. Apply the NetworkPolicy
   ```bash
   kubectl apply -f np.yaml
   ```

---

## 16) Export enabled Admission Controller Plugins

**Original prompt:**
> Write all Admission Controller Plugins, which are enabled in the kube-apiserver manifest,
> into `/root/admission-plugins`.

### I'm sorry, but you haven't provided the actual text for the first and second questions. Could you please share the specific questions you'd like to be rewritten?
1. Extract the `--enable-admission-plugins` line:
   ```bash
   grep -- '--enable-admission-plugins' /etc/kubernetes/manifests/kube-apiserver.yaml > /root/admission-plugins
   ```

---

## 17) Enable the MutatingAdmissionWebhook plugin

**Original prompt:**
> Enable the Admission Controller Plugin `MutatingAdmissionWebhook`.
> Tip: The apiserver manifest is under `/etc/kubernetes/manifests/kube-apiserver.yaml`.
> The argument we're looking for is `--enable-admission-plugins`.

### I'm sorry, but you haven't provided the actual text for the question to be rewritten. Could you please share the specific question you'd like to be rewritten?
1. Backup the existing manifest:
   ```bash
   cp /etc/kubernetes/manifests/kube-apiserver.yaml /root/kube-apiserver-backup.yaml
   ```
2. Edit the manifest and include `MutatingAdmissionWebhook` in `--enable-admission-plugins`:
   ```bash
   vim /etc/kubernetes/manifests/kube-apiserver.yaml
   ```
3. Save & exit (the kube-apiserver static pod will restart automatically).

---

## 18) Disable NamespaceLifecycle plugin and delete namespaces

**Original prompt:**
> Delete Namespace `space1`.
> Delete Namespace `default` (throws error).
> Disable the Admission Controller Plugin `NamespaceLifecycle` (not recommended).
> Now delete Namespace `default`.

### What are the steps involved in the process described in the first question?
1. Backup the manifest:
   ```bash
   cp /etc/kubernetes/manifests/kube-apiserver.yaml /root/kube-apiserver-nsl-backup.yaml
   ```
2. Edit the manifest to add `--disable-admission-plugins=NamespaceLifecycle`:
   ```bash
   vim /etc/kubernetes/manifests/kube-apiserver.yaml
   ```
3. Delete Namespace `space1`:
   ```bash
   kubectl delete ns space1
   ```
4. Delete Namespace `default`:
   ```bash
   kubectl delete ns default
   ```

---

## 19) Write Kubernetes server version to a file

**Original prompt:**
> Create file `/root/versions` with three lines:
> Major, Minor, Patch of the installed Kubernetes server version.

### What are the steps involved in deploying an application to Kubernetes?
1. Extract and split the server version:
   ```bash
   kubectl version --short | grep 'Server Version' | sed 's/.*Server Version: v//' | tr '.' '\n' > /root/versions
   ```

---

## 20) Write the API Group of Deployments to a file

**Original prompt:**
> Write the API Group of `Deployments` into `/root/group`.

### Based on the steps involved in deploying an application to Kubernetes, list them in detail.
1. Extract the group from `kubectl explain`:
   ```bash
   kubectl explain deployments | grep '^GROUP:' | awk '{print $2}' > /root/group
   ```

---

## 21) Update a CronJob to the non-deprecated API version

**Original prompt:**
> There is a CronJob file at `/apps/cronjob.yaml` which uses a deprecated API version.
> Update the file to use the non-deprecated one.

### What are the detailed steps involved in deploying an application to Kubernetes?
1. Backup and update the API version:
   ```bash
   cp /apps/cronjob.yaml /root/cronjob-backup.yaml
   sed -i 's@batch/v1beta1@batch/v1@g' /apps/cronjob.yaml
   ```
2. Apply the updated manifest:
   ```bash
   kubectl apply -f /apps/cronjob.yaml
   ```

---

## 22) Update a FlowSchema to the non-deprecated API version

**Original prompt:**
> There is a FlowSchema file at `/apps/flowschema.yaml` which uses a deprecated API version.
> Update the file to use the non-deprecated one.

### What are the detailed steps involved in deploying an application to Kubernetes, as previously described?
1. Backup and update the API version:
   ```bash
   cp /apps/flowschema.yaml /root/flowschema-backup.yaml
   sed -i 's@flowcontrol.apiserver.k8s.io/v1beta1@flowcontrol.apiserver.k8s.io/v1@g' /apps/flowschema.yaml
   ```
2. Apply the updated manifest:
   ```bash
   kubectl apply -f /apps/flowschema.yaml
   ```