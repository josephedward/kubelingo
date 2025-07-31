[ -f nginx.yaml ] && grep -q 'kind: Pod' nginx.yaml && grep -q 'name: nginx' nginx.yaml
