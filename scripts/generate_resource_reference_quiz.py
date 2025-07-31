#!/usr/bin/env python3
"""
Generate a YAML quiz manifest for Kubernetes resource references.

Each resource is tested on its shortname, API version, namespaced property, and Kind.
"""
resources = [
    ("bindings", "", "v1", True, "Binding"),
    ("componentstatuses", "cs", "v1", False, "ComponentStatus"),
    ("configmaps", "cm", "v1", True, "ConfigMap"),
    ("endpoints", "ep", "v1", True, "Endpoints"),
    ("events", "ev", "v1", True, "Event"),
    ("limitranges", "limits", "v1", True, "LimitRange"),
    ("namespaces", "ns", "v1", False, "Namespace"),
    ("nodes", "no", "v1", False, "Node"),
    ("persistentvolumeclaims", "pvc", "v1", True, "PersistentVolumeClaim"),
    ("persistentvolumes", "pv", "v1", False, "PersistentVolume"),
    ("pods", "po", "v1", True, "Pod"),
    ("podtemplates", "", "v1", True, "PodTemplate"),
    ("replicationcontrollers", "rc", "v1", True, "ReplicationController"),
    ("resourcequotas", "quota", "v1", True, "ResourceQuota"),
    ("secrets", "", "v1", True, "Secret"),
    ("serviceaccounts", "sa", "v1", True, "ServiceAccount"),
    ("services", "svc", "v1", True, "Service"),
    ("mutatingwebhookconfigurations", "", "admissionregistration.k8s.io/v1", False, "MutatingWebhookConfiguration"),
    ("validatingwebhookconfigurations", "", "admissionregistration.k8s.io/v1", False, "ValidatingWebhookConfiguration"),
    ("customresourcedefinitions", "crd,crds", "apiextensions.k8s.io/v1", False, "CustomResourceDefinition"),
    ("apiservices", "", "apiregistration.k8s.io/v1", False, "APIService"),
    ("controllerrevisions", "", "apps/v1", True, "ControllerRevision"),
    ("daemonsets", "ds", "apps/v1", True, "DaemonSet"),
    ("deployments", "deploy", "apps/v1", True, "Deployment"),
    ("replicasets", "rs", "apps/v1", True, "ReplicaSet"),
    ("statefulsets", "sts", "apps/v1", True, "StatefulSet"),
    ("tokenreviews", "", "authentication.k8s.io/v1", False, "TokenReview"),
    ("localsubjectaccessreviews", "", "authorization.k8s.io/v1", True, "LocalSubjectAccessReview"),
    ("selfsubjectaccessreviews", "", "authorization.k8s.io/v1", False, "SelfSubjectAccessReview"),
    ("selfsubjectrulesreviews", "", "authorization.k8s.io/v1", False, "SelfSubjectRulesReview"),
    ("subjectaccessreviews", "", "authorization.k8s.io/v1", False, "SubjectAccessReview"),
    ("horizontalpodautoscalers", "hpa", "autoscaling/v2", True, "HorizontalPodAutoscaler"),
    ("cronjobs", "cj", "batch/v1", True, "CronJob"),
    ("jobs", "", "batch/v1", True, "Job"),
    ("certificatesigningrequests", "csr", "certificates.k8s.io/v1", False, "CertificateSigningRequest"),
    ("leases", "", "coordination.k8s.io/v1", True, "Lease"),
    ("endpointslices", "", "discovery.k8s.io/v1", True, "EndpointSlice"),
    ("flowschemas", "", "flowcontrol.apiserver.k8s.io/v1beta2", False, "FlowSchema"),
    ("prioritylevelconfigurations", "", "flowcontrol.apiserver.k8s.io/v1beta2", False, "PriorityLevelConfiguration"),
    ("ingressclasses", "", "networking.k8s.io/v1", False, "IngressClass"),
    ("ingresses", "ing", "networking.k8s.io/v1", True, "Ingress"),
    ("networkpolicies", "netpol", "networking.k8s.io/v1", True, "NetworkPolicy"),
    ("runtimeclasses", "", "node.k8s.io/v1", False, "RuntimeClass"),
    ("poddisruptionbudgets", "pdb", "policy/v1", True, "PodDisruptionBudget"),
    ("podsecuritypolicies", "psp", "policy/v1beta1", False, "PodSecurityPolicy"),
    ("clusterrolebindings", "", "rbac.authorization.k8s.io/v1", False, "ClusterRoleBinding"),
    ("clusterroles", "", "rbac.authorization.k8s.io/v1", False, "ClusterRole"),
    ("rolebindings", "", "rbac.authorization.k8s.io/v1", True, "RoleBinding"),
    ("roles", "", "rbac.authorization.k8s.io/v1", True, "Role"),
    ("priorityclasses", "pc", "scheduling.k8s.io/v1", False, "PriorityClass"),
    ("csidrivers", "", "storage.k8s.io/v1", False, "CSIDriver"),
    ("csinodes", "", "storage.k8s.io/v1", False, "CSINode"),
    ("csistoragecapacities", "", "storage.k8s.io/v1", True, "CSIStorageCapacity"),
    ("storageclasses", "sc", "storage.k8s.io/v1", False, "StorageClass"),
    ("volumeattachments", "", "storage.k8s.io/v1", False, "VolumeAttachment"),
]
out = []
for resource, shortnames, api, ns, kind in resources:
    key = kind.lower()
    # Only include shortnames question if a shortname exists
    if shortnames:
        out.append((f"{key}::shortnames", f"What is the shortname for {kind}?", shortnames))
    out.append((f"{key}::apiversion", f"What is the API version for {kind}?", api))
    out.append((f"{key}::namespaced", f"Is {kind} a namespaced resource? (true/false)", str(ns).lower()))
    out.append((f"{key}::kind", f"What is the Kind name for the resource {kind}?", kind))

fm = ["# Resource Reference Quiz Manifest",
      "# Tests for each resource: shortnames, API version, namespaced, kind",
      "---"]
for qid, prompt, resp in out:
    # Only include shortnames questions when shortnames is non-empty
    if qid.endswith('::shortnames') and not resp:
        continue
    fm.append(f"- id: {qid}")
    fm.append(f"  question: \"{prompt}\"")
    fm.append("  type: command")
    fm.append("  metadata:")
    fm.append(f"    response: \"{resp}\"")
    fm.append("    category: \"Resource Reference\"")
    fm.append("    citation: \"https://kubernetes.io/docs/reference/generated/kubernetes-api/\"")
    fm.append("")

with open('question-data/yaml/manifests/resource_reference.yaml', 'w') as f:
    f.write("\n".join(fm))
print("Generated resource_reference.yaml with", len(out), "questions.")