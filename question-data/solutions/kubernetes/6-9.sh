kubectl get deployment frontend -o jsonpath='{.spec.template.spec.containers[0].image}' | grep 'nginx:1.14'
