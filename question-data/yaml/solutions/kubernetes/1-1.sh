[ -f deploy.yaml ] && grep -q 'kind: Deployment' deploy.yaml && grep -q 'name: nginx' deploy.yaml
