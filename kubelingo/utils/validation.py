import shlex

try:
    import yaml
except ImportError:
    yaml = None

try:
    from kubelingo_core import commands_equivalent, validate_yaml_structure
    RUST_CORE_AVAILABLE = True
except ImportError:
    RUST_CORE_AVAILABLE = False
    
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

    def commands_equivalent(user_cmd, expected_cmd):
        # Fallback Python implementation
        return normalize_command(user_cmd) == normalize_command(expected_cmd)
    
    def validate_yaml_structure(yaml_content_str):
        # Fallback Python implementation
        try:
            if yaml is None:
                return False, "PyYAML not installed"
            parsed = yaml.safe_load(yaml_content_str)
            
            if not parsed:
                return False, "Empty YAML content"
            if not isinstance(parsed, dict):
                return False, "YAML is not a dictionary"

            required = ["apiVersion", "kind", "metadata"]
            missing = [f for f in required if f not in parsed]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "YAML is valid"
        except Exception as e:
            return False, str(e)
