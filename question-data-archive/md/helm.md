# Managing Kubernetes with Helm

- Note: Helm is part of the new CKAD syllabus. Here are a few examples of using Helm to manage Kubernetes.

## Helm in K8s

### Creating a basic Helm chart

<details><summary>show</summary>
<p>

```bash
helm create chart-test ## this would create a helm 
```

</p>
</details>

### What are the steps to deploy an application using a Helm chart, assuming you have already created a basic Helm chart?

<details><summary>show</summary>
<p>

```bash
helm install -f myvalues.yaml myredis ./redis
```

</p>
</details>

### After deploying an application using a Helm chart, how can you find all pending Helm deployments across all namespaces?

<details><summary>show</summary>
<p>

```bash
helm list --pending -A
```

</p>
</details>

### How can you uninstall a Helm release after identifying pending Helm deployments across all namespaces?

<details><summary>show</summary>
<p>

```bash
helm uninstall -n namespace release_name
```

</p>
</details>

### What is the command to upgrade a Helm chart after uninstalling a Helm release, a process used for managing applications in Kubernetes?

<details><summary>show</summary>
<p>

```bash
helm upgrade -f myvalues.yaml -f override.yaml redis ./redis
```

</p>
</details>

### What is the command to add or update a Helm chart repository before upgrading a Helm chart, a necessary step when managing applications in Kubernetes?

<details><summary>show</summary>
<p>

Add, list, remove, update and index chart repos

```bash
helm repo add [NAME] [URL]  [flags]

helm repo list / helm repo ls

helm repo remove [REPO1] [flags]

helm repo update / helm repo up

helm repo update [REPO1] [flags]

helm repo index [DIR] [flags]
```

</p>
</details>

### What is the command to download a Helm chart from a repository after adding or updating the Helm chart repository, a step necessary when managing applications in Kubernetes?

<details><summary>show</summary>
<p>

```bash
helm pull [chart URL | repo/chartname] [...] [flags] ## this would download a helm, not install 
helm pull --untar [rep/chartname] # untar the chart after downloading it 
```

</p>
</details>

### What is the command to add the Bitnami repo located at https://charts.bitnami.com/bitnami to Helm, a step necessary before downloading Helm charts from this repository when managing applications in Kubernetes?
<details><summary>show</summary>
<p>
    
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
```
  
</p>
</details>

### After adding the Bitnami repo to Helm, a necessary step before downloading Helm charts for managing applications in Kubernetes, write the contents of the values.yaml file of the `bitnami/node` chart to standard output.
<details><summary>show</summary>
<p>
    
```bash
helm show values bitnami/node
```
  
</p>
</details>

### Install the `bitnami/node` chart using Helm, which is necessary for managing applications in Kubernetes after adding the Bitnami repo to Helm, setting the number of replicas to 5.
<details><summary>show</summary>
<p>

To achieve this, we need two key pieces of information:
- The name of the attribute in values.yaml which controls replica count
- A simple way to set the value of this attribute during installation

To identify the name of the attribute in the values.yaml file, we could get all the values, as in the previous task, and then grep to find attributes matching the pattern `replica`
```bash
helm show values bitnami/node | grep -i replica
```
which returns
```bash
## @param replicaCount Specify the number of replicas for the application
replicaCount: 1
```
 
We can use the `--set` argument during installation to override attribute values. Hence, to set the replica count to 5, we need to run
```bash
helm install mynode bitnami/node --set replicaCount=5
```

</p>
</details>


