"""
Kubernetes-specific quiz utilities: command normalization and comparison.
"""
import shlex
import random
import os
import tempfile
import subprocess

from kubelingo.gosandbox_integration import GoSandboxIntegration

# Aliases for kubectl verbs, resources, and flags
_VERB_ALIASES = {
    'apply': 'apply', 'create': 'create', 'get': 'get', 'describe': 'describe',
    'delete': 'delete', 'del': 'delete', 'rm': 'delete', 'scale': 'scale',
    'annotate': 'annotate', 'set': 'set', 'rollout': 'rollout',
}
_RESOURCE_ALIASES = {
    'po': 'pods', 'pod': 'pods', 'pods': 'pods',
    'svc': 'services', 'service': 'services', 'services': 'services',
    'deploy': 'deployments', 'deployment': 'deployments', 'deployments': 'deployments',
    'ns': 'namespaces', 'namespace': 'namespaces', 'namespaces': 'namespaces',
}
_FLAG_ALIASES = {
    '-n': '--namespace', '--namespace': '--namespace',
    '-o': '--output', '--output': '--output',
    '-f': '--filename', '--filename': '--filename',
    '--dry-run': '--dry-run', '--record': '--record',
    '--replicas': '--replicas', '--image': '--image',
}

def normalize_command(cmd_str):
    """Parse and normalize a kubectl command into canonical tokens."""
    tokens = shlex.split(cmd_str)
    tokens = [t.lower() for t in tokens]
    norm = []
    i = 0
    # command name
    if i < len(tokens) and tokens[i] == 'k':
        norm.append('kubectl')
        i += 1
    elif i < len(tokens):
        norm.append(tokens[i])
        i += 1
    # verb
    if i < len(tokens):
        norm.append(_VERB_ALIASES.get(tokens[i], tokens[i]))
        i += 1
    # resource
    if i < len(tokens) and not tokens[i].startswith('-'):
        norm.append(_RESOURCE_ALIASES.get(tokens[i], tokens[i]))
        i += 1
    # flags and positional args
    args = []
    flags = []
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith('-'):
            name = tok
            val = None
            if '=' in tok:
                name, val = tok.split('=', 1)
            else:
                if i + 1 < len(tokens) and not tokens[i+1].startswith('-'):
                    val = tokens[i+1]
                    i += 1
            name = _FLAG_ALIASES.get(name, name)
            flags.append(f"{name}={val}" if val is not None else name)
        else:
            args.append(tok)
        i += 1
    norm.extend(args)
    norm.extend(sorted(flags))
    return norm

def commands_equivalent(ans, expected):
    """Return True if two kubectl commands are equivalent after normalization."""
    return normalize_command(ans) == normalize_command(expected)
 
def handle_live_k8s_question(q, logger):
    """Handles a live Kubernetes question with an ephemeral EKS cluster."""
    # Avoid circular imports by loading CLI helpers here
    from kubelingo.cli import check_dependencies, Fore, Style
    is_correct = False
    # Ensure dependencies are available
    deps = check_dependencies('go', 'eksctl', 'kubectl')
    if deps:
        print(Fore.RED + f"Missing dependencies for live questions: {', '.join(deps)}. Skipping." + Style.RESET_ALL)
        return False, ''

    cluster_name = f"kubelingo-quiz-{random.randint(1000, 9999)}"
    kubeconfig_path = os.path.join(tempfile.gettempdir(), f"{cluster_name}.kubeconfig")
    user_yaml_str = ''
    try:
        # Acquire sandbox credentials
        print(Fore.YELLOW + "Acquiring AWS sandbox credentials via gosandbox..." + Style.RESET_ALL)
        gs = GoSandboxIntegration()
        creds = gs.acquire_credentials()
        if not creds:
            print(Fore.RED + "Failed to acquire AWS credentials. Cannot proceed with cloud exercise." + Style.RESET_ALL)
            return False, ''
        gs.export_to_environment()

        # Provision EKS cluster
        region = os.environ.get('AWS_REGION', 'us-west-2')
        node_type = os.environ.get('CLUSTER_INSTANCE_TYPE', 't3.medium')
        node_count = os.environ.get('NODE_COUNT', '2')
        print(Fore.YELLOW + f"Provisioning EKS cluster '{cluster_name}' "
                           f"(region={region}, nodes={node_count}, type={node_type})..." + Style.RESET_ALL)
        subprocess.run([
            'eksctl', 'create', 'cluster',
            '--name', cluster_name,
            '--region', region,
            '--nodegroup-name', 'worker-nodes',
            '--node-type', node_type,
            '--nodes', node_count
        ], check=True)

        # Write kubeconfig
        os.environ['KUBECONFIG'] = kubeconfig_path
        with open(kubeconfig_path, 'w') as kc:
            subprocess.run(['kubectl', 'config', 'view', '--raw'], stdout=kc, check=True)

        editor = os.environ.get('EDITOR', 'vim')
        # User edit loop
        while True:
            with tempfile.NamedTemporaryFile(mode='w+', suffix=".yaml", delete=False, encoding='utf-8') as tmp_yaml:
                tmp_yaml.write(q.get('starting_yaml', ''))
                tmp_path = tmp_yaml.name

            print(f"Opening a temp file in '{editor}' for you to edit...")
            try:
                subprocess.run([editor, tmp_path], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(Fore.RED + f"Error opening editor '{editor}': {e}. Skipping question." + Style.RESET_ALL)
                break

            with open(tmp_path, 'r', encoding='utf-8') as f:
                user_yaml_str = f.read()
            os.remove(tmp_path)

            print("Applying your YAML to the cluster...")
            apply_proc = subprocess.run([
                'kubectl', 'apply', '-f', '-'
            ], input=user_yaml_str, text=True, capture_output=True)
            if apply_proc.returncode != 0:
                print(Fore.RED + "Error applying YAML:" + Style.RESET_ALL)
                print(apply_proc.stderr)
            else:
                print("Running validation script...")
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".sh", delete=False, encoding='utf-8') as tmp_assert:
                    tmp_assert.write(q.get('assert_script', 'exit 1'))
                    assert_path = tmp_assert.name
                os.chmod(assert_path, 0o755)
                assert_proc = subprocess.run(['bash', assert_path], capture_output=True, text=True)
                os.remove(assert_path)
                if assert_proc.returncode == 0:
                    print(Fore.GREEN + "Correct!" + Style.RESET_ALL)
                    print(assert_proc.stdout)
                    is_correct = True
                    break
                else:
                    print(Fore.RED + "Incorrect. Validation failed:" + Style.RESET_ALL)
                    print(assert_proc.stdout or assert_proc.stderr)

            try:
                retry = input("Reopen editor to try again? [Y/n]: ").strip().lower()
            except EOFError:
                retry = 'n'
            if retry.startswith('n'):
                break
    finally:
        # Delete cluster and cleanup
        print(Fore.YELLOW + f"Deleting EKS cluster '{cluster_name}'..." + Style.RESET_ALL)
        subprocess.run([
            'eksctl', 'delete', 'cluster',
            '--name', cluster_name,
            '--region', os.environ.get('AWS_REGION', 'us-west-2')
        ], check=True)
        if os.path.exists(kubeconfig_path):
            os.remove(kubeconfig_path)
        if 'KUBECONFIG' in os.environ:
            del os.environ['KUBECONFIG']
    return is_correct, user_yaml_str
