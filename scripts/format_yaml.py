import re
import os

files_to_process = [
    "/Users/user/Documents/GitHub/kubelingo/questions/api_discovery_docs.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/app_configuration.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/commands_args_env.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/core_workloads.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/helm_basics.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/image_registry_use.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/imperative_vs_declarative.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/ingress_http_routing.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/jobs_cronjobs.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/kubectl_common_operations.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/kubectl_operations.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/labels_annotations_selectors.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/linux_syntax.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/namespaces_contexts.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/networking_utilities.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/observability_troubleshooting.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/persistence.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/pod_design_patterns.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/probes_health.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/resource_management.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/resource_reference.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/scheduling_hints.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/security_basics.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/service_accounts_in_apps.yaml",
    "/Users/user/Documents/GitHub/kubelingo/questions/services.yaml"
]

for file_path in files_to_process:
    with open(file_path, 'r') as f:
        content = f.read()

    def replace_solution(match):
        indent = match.group(1)
        solution_content_escaped = match.group(2)
        solution_content_unescaped = solution_content_escaped.replace('\n', '\n')

        content_indent = '  '

        indented_solution_lines = []
        for line in solution_content_unescaped.split('\n'):
            indented_solution_lines.append(content_indent + line)

        return f"{indent}solution: |\n" + '\n'.join(indented_solution_lines)

    modified_content = re.sub(r'(\s*solution: ")([^"]*)(")', replace_solution, content)

    with open(file_path, 'w') as f:
        f.write(modified_content)

print("YAML formatting updated for all specified files.")
