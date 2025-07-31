kubectl run curl1 --image=curlimages/curl -i -t --rm --restart=Never -- curl 10.244.0.4
