# Kubernetes Question Generation Tools Guide

## Core Validation Tools

### kube-score
```bash
# Basic usage for question validation
kube-score score question.yaml

# Example output for validation failures
kube-score score -o human question.yaml | grep FAIL
```

### yq/jq
```bash
# Extract metadata from question YAML
yq eval '.metadata' question.yaml

# Convert YAML to JSON for processing
yq eval -o json question.yaml | jq '.spec'

# Modify existing YAML
yq eval '.spec.replicas = 3' question.yaml -i
```

### Trivy
```bash 
# Security scan a question manifest
trivy config --severity HIGH,CRITICAL question.yaml

# Output JSON results for processing
trivy config -f json -o results.json question.yaml
```

## Advanced Templating

### Jsonnet Example
```jsonnet
// deployment.jsonnet
local kube = import 'kube.libsonnet';

{
  deployment: kube.Deployment('my-app') {
    spec: {
      replicas: 3,
      template: {
        spec: {
          containers: [
            kube.Container('app') {
              image: 'nginx:stable',
              ports: [{containerPort: 80}]
            }
          ]
        }
      }
    }
  }
}
```

```bash
# Generate YAML from Jsonnet
jsonnet -m outputs deployment.jsonnet
```

## Validation Workflow

1. Create initial question with kubectl:
```bash
kubectl create deployment my-app --image=nginx --dry-run=client -o yaml > question.yaml
```

2. Add complexity with yq:
```bash
yq eval '.spec.template.spec.containers[0].resources = {"limits": {"cpu": "100m"}}' -i question.yaml
```

3. Validate with kube-score:
```bash
kube-score score question.yaml
```

4. Security scan with Trivy:
```bash
trivy config --severity HIGH,CRITICAL question.yaml
```

5. Generate final output with Jsonnet:
```bash
jsonnet -y -m final_questions generated_question.jsonnet
```
