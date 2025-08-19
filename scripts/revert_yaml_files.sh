#!/bin/bash
files=(
"/Users/user/Documents/GitHub/kubelingo/questions/api_discovery_docs.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/app_configuration.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/commands_args_env.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/core_workloads.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/helm_basics.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/image_registry_use.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/imperative_vs_declarative.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/ingress_http_routing.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/jobs_cronjobs.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/kubectl_common_operations.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/kubectl_operations.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/labels_annotations_selectors.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/linux_syntax.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/namespaces_contexts.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/networking_utilities.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/observability_troubleshooting.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/persistence.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/pod_design_patterns.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/probes_health.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/resource_management.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/resource_reference.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/scheduling_hints.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/security_basics.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/service_accounts_in_apps.yaml"
"/Users/user/Documents/GitHub/kubelingo/questions/services.yaml"
)

for file in "${files[@]}"; do
  git restore "$file"
done
