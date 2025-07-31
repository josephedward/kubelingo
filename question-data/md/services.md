![](https://gaforgithub.azurewebsites.net/api?repo=CKAD-exercises/services&empty)
# Services and Networking (13%)

### Create a pod with image nginx called nginx and expose its port 80

<details><summary>show</summary>
<p>

```bash
kubectl run nginx --image=nginx --restart=Never --port=80 --expose
# observe that a pod as well as a service are created
```

</p>
</details>


### After creating a pod with the image nginx called nginx and exposing its port 80, confirm that a ClusterIP has been created for it. Also, check the endpoints associated with this configuration.

<details><summary>show</summary>
<p>

```bash
kubectl get svc nginx # services
kubectl get ep # endpoints
```

</p>
</details>

### Retrieve the ClusterIP of the service created for a pod using the nginx image and exposed on port 80, then create a temporary busybox pod and use wget to 'hit' the retrieved ClusterIP.

<details><summary>show</summary>
<p>

```bash
kubectl get svc nginx # get the IP (something like 10.108.93.130)
kubectl run busybox --rm --image=busybox -it --restart=Never --
wget -O- [PUT THE POD'S IP ADDRESS HERE]:80
exit
```

</p>
or
<p>

```bash
IP=$(kubectl get svc nginx --template={{.spec.clusterIP}}) # get the IP (something like 10.108.93.130)
kubectl run busybox --rm --image=busybox -it --restart=Never --env="IP=$IP" -- wget -O- $IP:80 --timeout 2
# Tip: --timeout is optional, but it helps to get answer more quickly when connection fails (in seconds vs minutes)
```

</p>
</details>

### Convert the ClusterIP service, which was created for a pod using the nginx image and exposed on port 80, to a NodePort service and find the NodePort port number. Then, use the Node's IP address to access the service. Finally, delete both the service and the pod.

<details><summary>show</summary>
<p>

```bash
kubectl edit svc nginx
```

```yaml
apiVersion: v1
kind: Service
metadata:
  creationTimestamp: 2018-06-25T07:55:16Z
  name: nginx
  namespace: default
  resourceVersion: "93442"
  selfLink: /api/v1/namespaces/default/services/nginx
  uid: 191e3dac-784d-11e8-86b1-00155d9f663c
spec:
  clusterIP: 10.97.242.220
  ports:
  - port: 80
    protocol: TCP
    targetPort: 80
  selector:
    run: nginx
  sessionAffinity: None
  type: NodePort # change cluster IP to nodeport
status:
  loadBalancer: {}
```

or

```bash
kubectl patch svc nginx -p '{"spec":{"type":"NodePort"}}' 
```

```bash
kubectl get svc
```

```
# result:
NAME         TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
kubernetes   ClusterIP   10.96.0.1        <none>        443/TCP        1d
nginx        NodePort    10.107.253.138   <none>        80:31931/TCP   3m
```

```bash
wget -O- NODE_IP:31931 # if you're using Kubernetes with Docker for Windows/Mac, try 127.0.0.1
#if you're using minikube, try minikube ip, then get the node ip such as 192.168.99.117
```

```bash
kubectl delete svc nginx # Deletes the service
kubectl delete pod nginx # Deletes the pod
```
</p>
</details>

### Create a deployment called foo using the image 'dgkanatsios/simpleapp', which is a simple server that returns the hostname, and ensure this deployment has 3 replicas. Apply the label 'app=foo' to the deployment. Configure the deployment so that the containers within the pods will accept traffic on port 8080. This task follows the previous exercise where you converted a ClusterIP service for a pod running the nginx image and exposed on port 80 to a NodePort service, accessed it using the Node's IP address, and then deleted both the service and the pod. For this new task, do NOT create a service for the deployment yet.

<details><summary>show</summary>
<p>

```bash
kubectl create deploy foo --image=dgkanatsios/simpleapp --port=8080 --replicas=3
kubectl label deployment foo --overwrite app=foo #This is optional since kubectl create deploy foo will create label app=foo by default
```
</p>
</details>

### After creating a deployment called foo with the image 'dgkanatsios/simpleapp', which has 3 replicas and is configured to accept traffic on port 8080, get the pod IPs. Then, create a temporary busybox pod and try hitting the foo deployment pod IPs on port 8080.

<details><summary>show</summary>
<p>


```bash
kubectl get pods -l app=foo -o wide # 'wide' will show pod IPs
kubectl run busybox --image=busybox --restart=Never -it --rm -- sh
wget -O- <POD_IP>:8080 # do not try with pod name, will not work
# try hitting all IPs generated after running 1st command to confirm that hostname is different
exit
# or
kubectl get po -o wide -l app=foo | awk '{print $6}' | grep -v IP | xargs -L1 -I '{}' kubectl run --rm -ti tmp --restart=Never --image=busybox -- wget -O- http://\{\}:8080
# or
kubectl get po -l app=foo -o jsonpath='{range .items[*]}{.status.podIP}{"\n"}{end}' | xargs -L1 -I '{}' kubectl run --rm -ti tmp --restart=Never --image=busybox -- wget -O- http://\{\}:8080
```

</p>
</details>

### Create a service that exposes the deployment called foo, which uses the image 'dgkanatsios/simpleapp', has 3 replicas, and is configured to accept traffic on port 8080, on a new port 6262. Verify the service's existence and check the endpoints.

<details><summary>show</summary>
<p>


```bash
kubectl expose deploy foo --port=6262 --target-port=8080
kubectl get service foo # you will see ClusterIP as well as port 6262
kubectl get endpoints foo # you will see the IPs of the three replica pods, listening on port 8080
```

</p>
</details>

### Create a temporary busybox pod and use wget to connect to the service named 'foo', which exposes a deployment called foo using the image 'dgkanatsios/simpleapp', with 3 replicas, configured to accept traffic on port 8080, and is exposed on a new port 6262. Verify that each time there's a different hostname returned to demonstrate load balancing between the replicas. After testing, delete the deployment named foo and its associated services to clean up the cluster.

<details><summary>show</summary>
<p>

```bash
kubectl get svc # get the foo service ClusterIP
kubectl run busybox --image=busybox -it --rm --restart=Never -- sh
wget -O- foo:6262 # DNS works! run it many times, you'll see different pods responding
wget -O- <SERVICE_CLUSTER_IP>:6262 # ClusterIP works as well
# you can also kubectl logs on deployment pods to see the container logs
kubectl delete svc foo
kubectl delete deploy foo
```

</p>
</details>

### After creating a temporary busybox pod to connect to a previously mentioned service named 'foo' that exposes a deployment with 3 replicas, using the image 'dgkanatsios/simpleapp', and verifying load balancing by observing different hostnames, proceed to the next task. Create an nginx deployment of 2 replicas and expose it via a ClusterIP service on port 80. Then, create a NetworkPolicy that allows only pods labeled with 'access: granted' to access the nginx deployment's pods. Apply this policy to enforce the specified access control.

kubernetes.io > Documentation > Concepts > Services, Load Balancing, and Networking > [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

> Note that network policies may not be enforced by default, depending on your k8s implementation. E.g. Azure AKS by default won't have policy enforcement, the cluster must be created with an explicit support for `netpol` https://docs.microsoft.com/en-us/azure/aks/use-network-policies#overview-of-network-policy  
  
<details><summary>show</summary>
<p>

```bash
kubectl create deployment nginx --image=nginx --replicas=2
kubectl expose deployment nginx --port=80

kubectl describe svc nginx # see the 'app=nginx' selector for the pods
# or
kubectl get svc nginx -o yaml

vi policy.yaml
```

```YAML
kind: NetworkPolicy
apiVersion: networking.k8s.io/v1
metadata:
  name: access-nginx # pick a name
spec:
  podSelector:
    matchLabels:
      app: nginx # selector for the pods
  ingress: # allow ingress traffic
  - from:
    - podSelector: # from pods
        matchLabels: # with this label
          access: granted
```

```bash
# Create the NetworkPolicy
kubectl create -f policy.yaml

# Check if the Network Policy has been created correctly
# make sure that your cluster's network provider supports Network Policy (https://kubernetes.io/docs/tasks/administer-cluster/declare-network-policy/#before-you-begin)
kubectl run busybox --image=busybox --rm -it --restart=Never -- wget -O- http://nginx:80 --timeout 2                          # This should not work. --timeout is optional here. But it helps to get answer more quickly (in seconds vs minutes)
kubectl run busybox --image=busybox --rm -it --restart=Never --labels=access=granted -- wget -O- http://nginx:80 --timeout 2  # This should be fine
```

</p>
</details>
