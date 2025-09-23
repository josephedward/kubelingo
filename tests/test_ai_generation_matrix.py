import os
import pytest
import yaml

from kubelingo.provider_adapter import generate_with_provider, ProviderError


# 36 curated subjects (match app menus exactly)
SUBJECTS = [
    'Api Discovery Docs',
    'App Configuration',
    'Commands Args Env',
    'Configmap',
    'Core Workloads',
    'Deployment',
    'Helm Basics',
    'Image Registry Use',
    'Imperative Vs Declarative',
    'Ingress Http Routing',
    'Jobs Cronjobs',
    'Kubectl Common Operations',
    'Kubectl Operations',
    'Labels Annotations Selectors',
    'Linux Commands Syntax',
    'Logging',
    'Namespaces Contexts',
    'Networking Utilities',
    'Observability Troubleshooting',
    'Persistence',
    'Pod Design Patterns',
    'Probes Health',
    'Resource Management',
    'Resource Reference',
    'Scheduling Hints',
    'Security Basics',
    'Service Accounts In Apps',
    'Services',
    'RBAC',
    'Monitoring',
    'Troubleshooting',
    'Pod',
    'Service',
    'Secret',
    'PVC',
    'Job',
]


PROVIDERS = [
    ("gemini", "GEMINI_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("perplexity", "PERPLEXITY_API_KEY"),
]

QUESTION_TYPES = [
    "vocab",
    "true_false",
    "mcq",
    "commands",
    "manifests",
]


def _slugify(label: str) -> str:
    return '_'.join(label.strip().lower().split())


def _has_module_for_provider(name: str) -> bool:
    try:
        if name == "gemini":
            import google.generativeai  # noqa: F401
        elif name == "openai":
            import openai  # noqa: F401
        # openrouter and perplexity use requests only (already a dep)
        return True
    except Exception:
        return False


@pytest.mark.network
@pytest.mark.parametrize("provider,env_var", PROVIDERS)
@pytest.mark.parametrize("qtype", QUESTION_TYPES)
@pytest.mark.parametrize("subject", SUBJECTS)
def test_ai_generation_matrix(provider, env_var, qtype, subject):
    # Skip if required API key is not present
    if not os.getenv(env_var):
        pytest.skip(f"Missing API key for provider {provider}: {env_var}")

    # Skip if optional client library is not installed
    if not _has_module_for_provider(provider):
        pytest.skip(f"Client library for provider {provider} is not installed")

    topic = _slugify(subject)

    try:
        result = generate_with_provider(provider, qtype, topic)
    except ProviderError as e:
        # Surface provider gaps explicitly when network tests are enabled
        pytest.fail(f"ProviderError for {provider}/{qtype}/{subject}: {e}")

    # Minimal schema assertions common to all question types
    assert isinstance(result, dict), "Provider must return a JSON object"
    assert result.get("type") == qtype
    assert result.get("topic") == topic
    assert isinstance(result.get("question", ""), str) and result["question"].strip()
    assert "suggested_answer" in result, "Missing suggested_answer"

    # Type-specific validations
    if qtype == "mcq":
        opts = result.get("options")
        assert isinstance(opts, list) and len(opts) == 4, "MCQ must include exactly 4 options"

    if qtype == "true_false":
        ans = str(result.get("suggested_answer", "")).strip().lower()
        assert ans in {"true", "false"}, "True/False must be 'true' or 'false'"

    if qtype == "commands":
        cmd = result.get("suggested_answer")
        assert isinstance(cmd, str) and cmd.strip(), "Command answer must be a non-empty string"

    if qtype == "manifests":
        yml = result.get("suggested_answer")
        assert isinstance(yml, str) and yml.strip(), "Manifest answer must be YAML string"
        try:
            obj = yaml.safe_load(yml)
        except Exception as e:
            pytest.fail(f"Manifest YAML did not parse: {e}\n---\n{yml}")
        assert isinstance(obj, (dict, list)), "Manifest YAML must parse to a mapping or list"
        # If dict, check for core fields
        if isinstance(obj, dict):
            assert "apiVersion" in obj and "kind" in obj, "Manifest must include apiVersion and kind"

