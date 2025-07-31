kubectl get deployment webapp -o jsonpath='{.spec.template.spec.containers[0].image}' | grep 'nginx:1.18'
