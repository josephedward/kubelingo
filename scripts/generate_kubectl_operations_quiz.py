#!/usr/bin/env python3
import os

"""
Generate the Kubectl Operations quiz manifest based on kubectl reference.
This creates question-data/yaml/kubectl_operations.yaml
"""
ops = [
    ("alpha", "List the available commands that correspond to alpha features, which are not enabled in Kubernetes clusters by default."),
    ("annotate", "Add or update the annotations of one or more resources."),
    ("api-resources", "List the API resources that are available."),
    ("api-versions", "List the API versions that are available."),
    ("apply", "Apply or Update a resource from a file or stdin."),
    ("attach", "Attach to a running container either to view the output stream or interact with the container (stdin)."),
    ("auth", "Inspect authorization."),
    ("autoscale", "Automatically scale the set of pods that are managed by a replication controller."),
    ("certificate", "Modify certificate resources."),
    ("cluster-info", "Display endpoint information about the master and services in the cluster."),
    ("completion", "Output shell completion code for the specified shell (bash or zsh)."),
    ("config", "Modify kubeconfig files via subcommands."),
    ("convert", "Convert config files between different API versions."),
    ("cordon", "Mark a node as unschedulable."),
    ("cp", "Copy files and directories to and from containers."),
    ("create", "Create one or more resources from a file or stdin."),
    ("delete", "Delete resources either from a file, stdin, or specifying label selectors, names, or resource selectors."),
    ("describe", "Display the detailed state of one or more resources."),
    ("diff", "Diff file or stdin against live configuration."),
    ("drain", "Drain a node in preparation for maintenance."),
    ("edit", "Edit and update the definition of one or more resources on the server by using the default editor."),
    ("events", "List events."),
    ("exec", "Execute a command against a container in a pod."),
    ("explain", "Get documentation of various resources using kubectl explain."),
    ("expose", "Expose a resource (service, pod, or RC) as a new service."),
    ("get", "List one or more resources."),
    ("kustomize", "Build resources from a kustomization directory."),
    ("label", "Add or update the labels of one or more resources."),
    ("logs", "Print the logs for a container in a pod."),
    ("options", "List global command-line options for kubectl."),
    ("patch", "Update one or more fields of a resource using a patch."),
    ("plugin", "Provides utilities for interacting with kubectl plugins."),
    ("port-forward", "Forward one or more local ports to a pod."),
    ("proxy", "Run a proxy to the Kubernetes API server."),
    ("replace", "Replace a resource from a file or stdin."),
    ("rollout", "Manage the rollout of a resource like deployments, daemonsets, statefulsets."),
    ("run", "Run a specified image on the cluster."),
    ("scale", "Update the size of a resource (replica count)."),
    ("set", "Configure application resources using subcommands."),
    ("taint", "Update the taints on one or more nodes."),
    ("top", "Display resource usage of pods or nodes."),
    ("uncordon", "Mark a node as schedulable."),
    ("version", "Display the Kubernetes version running on client and server."),
    ("wait", "Wait for a specific condition on one or many resources.")
]
def generate():
    """Generates the kubectl_operations.yaml quiz manifest."""
    out = ["# Kubectl Operations Quiz Manifest",
           "# Ask for operation names by description.",
           "---"]
    for op, desc in ops:
        out.append(f"- id: kubectl::{op}")
        out.append(f"  question: \"{desc}\"")
        out.append("  type: command")
        out.append("  metadata:")
        out.append(f"    response: \"{op}\"")
        out.append("    validator:")
        out.append("      type: ai")
        out.append(f"      expected: \"{op}\"")
        out.append("    category: \"Kubectl Operations\"")
        out.append("    citation: \"https://kubernetes.io/docs/reference/kubectl/#operations\"")
        out.append("")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(project_root, 'question-data/yaml/kubectl_operations.yaml')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write("\n".join(out))
    print(f"Generated kubectl_operations.yaml with {len(ops)} questions.")

if __name__ == '__main__':
    generate()
