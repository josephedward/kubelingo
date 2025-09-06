import requests
import yaml
import re
import random
from functools import lru_cache

# Define repositories and their mappings to Kubelingo topics
# This mapping defines where to search for questions for each Kubelingo topic.
TOPIC_REPO_MAPPING = {
    # Manifest-based questions (from Container Solutions examples)
    "core_workloads": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["Deployment", "ReplicaSet", "StatefulSet", "DaemonSet"]},
    "pod_design_patterns": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["Pod"]},
    "services": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["Service"]},
    "jobs_cronjobs": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["Job", "CronJob"]},
    "ingress_http_routing": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["Ingress"]},
    "persistence": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["PersistentVolume", "PersistentVolumeClaim"]},
    "app_configuration": {"repo": "ContainerSolutions/kubernetes-examples", "branch": "master", "question_type": "manifest", "subjects": ["ConfigMap", "Secret"]},

    # Command-based questions (from dgkanatsios/CKAD-exercises)
    # The 'path_prefix' helps narrow down the search within the repository.
    "kubectl_common_operations": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"},
    "kubectl_operations": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"}, # General operations often in core concepts
    "imperative_vs_declarative": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"}, # Often covered in core concepts
    "api_discovery_docs": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"},
    "image_registry_use": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "2.Pod_Design"},
    "labels_annotations_selectors": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"},
    "namespaces_contexts": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"},
    "networking_utilities": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "5.Services_and_Networking"},
    "observability_troubleshooting": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "4.Observability"},
    "probes_health": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "4.Observability"},
    "resource_management": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"},
    "scheduling_hints": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "1.Core_Concepts"},
    "security_basics": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "7.Security"},
    "service_accounts_in_apps": {"repo": "dgkanatsios/CKAD-exercises", "branch": "main", "question_type": "command", "path_prefix": "7.Security"},
    # Topics not directly mapped to external repos or requiring manual review:
    "helm_basics": None, # No direct external repo mapping for questions
    "linux_syntax": None, # Not Kubernetes specific
    "resource_reference": None, # General reference, not question-based
}


@lru_cache(maxsize=1)
def get_repo_tree(owner, repo, branch="main"):
    """
    Get the file tree of a GitHub repository.
    Caches the result to avoid repeated API calls for the same repo.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching repo tree for {owner}/{repo}: {e}")
        return None

def filter_files(tree_data, extensions, path_prefix=""):
    """
    Filter files from the repo tree by extension and path prefix.
    """
    if not tree_data:
        return []
    files = []
    for item in tree_data.get("tree", []):
        path = item.get("path", "")
        # Ensure path starts with the prefix and ends with one of the extensions
        if path.startswith(path_prefix) and path.endswith(extensions) and item.get("type") == "blob":
            files.append(item)
    return files

def fetch_file_content(url):
    """
    Fetch the content of a file from a URL.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file content from {url}: {e}")
        return None

def validate_kubernetes_manifest(content):
    """
    Validate if content is a proper Kubernetes manifest.
    """
    try:
        manifest = yaml.safe_load(content)
        if not isinstance(manifest, dict):
            return False
        required_fields = ["apiVersion", "kind"]
        if not all(field in manifest for field in required_fields):
            return False
        valid_kinds = [
            "Pod", "Deployment", "Service", "ConfigMap",
            "Secret", "Ingress", "Job", "CronJob", "DaemonSet",
            "StatefulSet", "DaemonSet", "ReplicaSet", "PersistentVolume",
            "PersistentVolumeClaim", "ServiceAccount", "NetworkPolicy",
            "Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding",
            "CustomResourceDefinition", "HorizontalPodAutoscaler",
            "PodDisruptionBudget", "LimitRange", "ResourceQuota",
            "PriorityClass", "PodSecurityPolicy", "ValidatingWebhookConfiguration",
            "MutatingWebhookConfiguration", "Lease", "EndpointSlice",
            "IngressClass", "RuntimeClass", "StorageClass", "VolumeSnapshot",
            "VolumeSnapshotContent", "CertificateSigningRequest", "FlowSchema",
            "PriorityLevelConfiguration", "APIService", "Binding", "ComponentStatus",
            "Event", "Eviction", "LimitRange", "Node", "PersistentVolume",
            "PersistentVolumeClaim", "Pod", "PodTemplate", "ReplicationController",
            "ResourceQuota", "Secret", "Service", "ServiceAccount", "Binding",
            "ConfigMap", "Endpoint", "Event", "LimitRange", "Namespace",
            "Node", "PersistentVolume", "PersistentVolumeClaim", "Pod",
            "PodTemplate", "ReplicationController", "ResourceQuota", "Secret",
            "Service", "ServiceAccount", "Binding", "ConfigMap", "Endpoint",
            "Event", "LimitRange", "Namespace", "Node", "PersistentVolume",
            "PersistentVolumeClaim", "Pod", "PodTemplate", "ReplicationController",
            "ResourceQuota", "Secret", "Service", "ServiceAccount"
        ]
        return manifest.get("kind") in valid_kinds
    except yaml.YAMLError:
        return False

def extract_questions_and_answers_from_readme(content):
    """
    Extracts questions and answers from README files.
    Questions are lines ending with 'show', and answers are in the following bash block.
    """
    qa_pairs = []
    # Regex to find questions (lines ending in 'show') and the following code block.
    # It captures the question text and the content of the bash block.
    pattern = re.compile(r"(.*?show\s*\n+```(?:bash|yaml|json)\n(.*?)\n```)", re.DOTALL)
    matches = pattern.findall(content)
    
    for match in matches:
        full_block_text = match[0] # The entire matched block including question and code
        answer_code = match[1].strip() # The content of the code block

        # Extract the question text, which is the line ending with 'show'
        question_lines = full_block_text.split('\n')
        question = ""
        for line in reversed(question_lines): # Search from bottom up to find the 'show' line before the code block
            if line.strip().endswith('show'):
                question = line.strip().replace('show', '').strip()
                # Clean up markdown headers if present
                question = re.sub(r'^(#+\s*)', '', question)
                break
        
        if question and answer_code:
            qa_pairs.append({"question": question, "suggestion": [answer_code]})
            
    return qa_pairs

def search_for_questions(topic_name, question_type=None, subject=None):
    """
    Main function to search for questions in the configured repositories for a specific topic.
    :param topic_name: The topic to search for questions on (e.g., 'core_workloads').
    :param question_type: The type of question ('command' or 'manifest'). If None, it's derived from TOPIC_REPO_MAPPING.
    :param subject: The subject matter to filter by (e.g., 'Pod', 'Deployment'). Only for 'manifest' type.
    """
    all_questions = []
    
    if topic_name not in TOPIC_REPO_MAPPING or TOPIC_REPO_MAPPING[topic_name] is None:
        print(f"Error: No repository mapping found for topic '{topic_name}'.")
        return []

    repo_info = TOPIC_REPO_MAPPING[topic_name]
    owner, repo = repo_info["repo"].split('/')
    branch = repo_info["branch"]
    path_prefix = repo_info.get("path_prefix", "")
    
    # Use question_type from mapping if not explicitly provided
    if question_type is None:
        question_type = repo_info.get("question_type")

    if question_type not in ["command", "manifest"]:
        print(f"Error: Invalid question_type '{question_type}' for topic '{topic_name}'. Must be 'command' or 'manifest'.")
        return []

    tree_data = get_repo_tree(owner, repo, branch)
    if not tree_data:
        return []

    if question_type == "command":
        # For command questions, we typically look in Markdown files (like READMEs)
        files_to_process = filter_files(tree_data, (".md", ".txt"), path_prefix=path_prefix)
        for file_item in files_to_process:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_item['path']}"
            content = fetch_file_content(raw_url)
            if content:
                # Use the specialized function for extracting Q&A from READMEs
                qa_pairs = extract_questions_and_answers_from_readme(content)
                if qa_pairs:
                    all_questions.extend(qa_pairs)
    
    elif question_type == "manifest":
        # For manifest questions, we look for YAML files
        files_to_process = filter_files(tree_data, (".yaml", ".yml"), path_prefix=path_prefix)
        for file_item in files_to_process:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_item['path']}"
            content = fetch_file_content(raw_url)
            if content and validate_kubernetes_manifest(content):
                # If a subject is specified, filter by manifest kind
                if subject:
                    try:
                        manifest = yaml.safe_load(content)
                        if manifest.get('kind', '').lower() == subject.lower():
                            # For manifests, the "question" is a prompt, and the content is the suggestion/solution
                            all_questions.append({
                                "question": f"Create a Kubernetes resource of kind '{manifest.get('kind', 'unknown')}' with the following manifest:",
                                "suggestion": [content],
                                "solution": [content]
                            })
                    except yaml.YAMLError:
                        continue # Skip if not valid YAML
                else:
                    # If no subject, add all valid manifests
                    manifest = yaml.safe_load(content) # Reload to get kind
                    all_questions.append({
                        "question": f"Create a Kubernetes resource of kind '{manifest.get('kind', 'unknown')}' with the following manifest:",
                        "suggestion": [content],
                        "solution": [content]
                    })

    return all_questions

def get_random_question_from_search(topic_name, question_type=None, subject=None):
    """
    Get a single random question from the search results for a given topic.
    This function is primarily for internal use by the CLI.
    """
    questions = search_for_questions(topic_name, question_type, subject)
    if not questions:
        return None # Return None if no questions found

    return random.choice(questions)

def search_for_quality_questions():
    """
    Search for quality questions and manifests across all configured topics.
    Prints summary of number of questions found per topic (and subject for manifests).
    """
    for topic_name, repo_info in TOPIC_REPO_MAPPING.items():
        # Skip topics with no repository mapping
        if repo_info is None:
            continue
        q_type = repo_info.get('question_type')
        subjects = repo_info.get('subjects')
        # For manifest questions, search per subject; else, single search
        subject_list = subjects if (q_type == 'manifest' and subjects) else [None]
        for subject in subject_list:
            # Perform search
            questions = search_for_questions(topic_name, question_type=q_type, subject=subject)
            count = len(questions)
            # Print summary line
            if subject:
                print(f"{topic_name} ({q_type}, subject={subject}): {count} questions")
            else:
                print(f"{topic_name} ({q_type}): {count} questions")

if __name__ == '__main__':
    # Example of how to use the functions
    print("--- Searching for 'kubectl_common_operations' (command type) ---")
    # Note: For command questions, the 'suggestion' will contain the command.
    # The 'question' field will be the extracted question text.
    command_questions = search_for_questions(topic_name="kubectl_common_operations", question_type="command")
    print(f"Found {len(command_questions)} command questions.")
    if command_questions:
        print("Here are some examples:")
        for q in random.sample(command_questions, min(3, len(command_questions))):
            print(f"- Q: {q['question']}\n  A: {q['suggestion'][0]}")

    print("\n--- Searching for 'pod_design_patterns' (manifest type, subject Pod) ---")
    # Note: For manifest questions, the 'suggestion' will contain the manifest YAML.
    # The 'question' field will be a generic prompt.
    manifest_questions = search_for_questions(topic_name="pod_design_patterns", question_type="manifest", subject="Pod")
    print(f"Found {len(manifest_questions)} manifest questions.")
    if manifest_questions:
        print("Here is a random manifest question:")
        q = random.choice(manifest_questions)
        print(f"- Q: {q['question']}\n  A: {q['suggestion'][0]}")

    print("\n--- Getting a random question for 'services' (manifest type) ---")
    random_service_manifest_q = get_random_question_from_search(topic_name="services", question_type="manifest")
    if random_service_manifest_q:
        print(f"Q: {random_service_manifest_q['question']}\nA: {random_service_manifest_q['suggestion'][0]}")
    else:
        print("No random service manifest question found.")
