[ -f webapp.yaml ] && grep -q 'kind: Pod' webapp.yaml && grep -q 'name: webapp' webapp.yaml
