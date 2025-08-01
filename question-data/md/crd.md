# Extend the Kubernetes API with CRD (CustomResourceDefinition)

- Note: CRD is part of the new CKAD syllabus. Here are a few examples of installing custom resource into the Kubernetes API by creating a CRD.

## CRD in K8s

### Create a CustomResourceDefinition manifest file for an Operator with the following specifications :
* *Name* : `operators.stable.example.com`
* *Group* : `stable.example.com`
* *Schema*: `<email: string><name: string><age: integer>`
* *Scope*: `Namespaced`
* *Names*: `<plural: operators><singular: operator><shortNames: op>`
* *Kind*: `Operator`

<details><summary>show</summary>
<p>

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  # name must match the spec fields below, and be in the form: <plural>.<group>
  name: operators.stable.example.com
spec:
  group: stable.example.com
  versions:
    - name: v1
      served: true
      # One and only one version must be marked as the storage version.
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                email:
                  type: string
                name:
                  type: string
                age:
                  type: integer
  scope: Namespaced
  names:
    plural: operators
    singular: operator
    # kind is normally the CamelCased singular type. Your resource manifests use this.
    kind: Operator
    shortNames:
    - op
```

</p>
</details>

### Create the CustomResourceDefinition (CRD) resource in the Kubernetes (K8S) API based on the manifest file for an Operator with the specified specifications.

<details><summary>show</summary>
<p>

```bash
kubectl apply -f operator-crd.yml
```

</p>
</details>

### Create a custom object from the CustomResourceDefinition (CRD) resource you previously created in the Kubernetes API for an Operator, based on the specified specifications in the manifest file.

* *Name* : `operator-sample`
* *Kind*: `Operator`
* Spec:
  * email: `operator-sample@stable.example.com`
  * name: `operator sample`
  * age: `30`

<details><summary>show</summary>
<p>

```yaml
apiVersion: stable.example.com/v1
kind: Operator
metadata:
  name: operator-sample
spec:
  email: operator-sample@stable.example.com
  name: "operator sample"
  age: 30
```

```bash
kubectl apply -f operator.yml
```

</p>
</details>

### List the custom object you created from the CustomResourceDefinition (CRD) in the Kubernetes API for an Operator, as specified in the previous question's manifest file.

<details><summary>show</summary>
<p>

Use singular, plural and short forms

```bash
kubectl get operators
or
kubectl get operator
or
kubectl get op
```

</p>
</details>
