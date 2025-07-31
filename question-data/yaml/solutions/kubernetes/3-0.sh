kubectl get cm app-config -o yaml | grep 'APP_COLOR: blue' && kubectl get cm app-config -o yaml | grep 'APP_MODE: prod'
