kubectl get deployment webapp -o jsonpath='{.spec.replicas}' | grep 3 && kubectl get deployment webapp -o jsonpath='{.spec.template.spec.containers[0].image}' | grep 'nginx:1.17'
