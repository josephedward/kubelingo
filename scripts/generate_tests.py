#!/usr/bin/env python3
"""
Generate parametrized AI generation tests (4 providers x 5 types x 36 subjects).

Writes tests/test_ai_generation_matrix.py. Safe to re-run.
"""

from pathlib import Path

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

TEMPLATE = """import os
import pytest
import yaml

from kubelingo.provider_adapter import generate_with_provider, ProviderError

SUBJECTS = {subjects}

PROVIDERS = [
    ("gemini", "GEMINI_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("perplexity", "PERPLEXITY_API_KEY"),
]

QUESTION_TYPES = ["vocab", "true_false", "mcq", "commands", "manifests"]

def _slugify(label: str) -> str:
    return '_'.join(label.strip().lower().split())

def _has_module_for_provider(name: str) -> bool:
    try:
        if name == "gemini":
            import google.generativeai  # noqa: F401
        elif name == "openai":
            import openai  # noqa: F401
        return True
    except Exception:
        return False

@pytest.mark.network
@pytest.mark.parametrize("provider,env_var", PROVIDERS)
@pytest.mark.parametrize("qtype", QUESTION_TYPES)
@pytest.mark.parametrize("subject", SUBJECTS)
def test_ai_generation_matrix(provider, env_var, qtype, subject):
    if not os.getenv(env_var):
        pytest.skip(f"Missing API key for provider {provider}: {env_var}")
    if not _has_module_for_provider(provider):
        pytest.skip(f"Client library for provider {provider} is not installed")
    topic = _slugify(subject)
    try:
        result = generate_with_provider(provider, qtype, topic)
    except ProviderError as e:
        pytest.fail(f"ProviderError for {provider}/{qtype}/{subject}: {e}")
    assert isinstance(result, dict)
    assert result.get("type") == qtype
    assert result.get("topic") == topic
    assert isinstance(result.get("question", ""), str) and result["question"].strip()
    assert "suggested_answer" in result
    if qtype == "mcq":
        opts = result.get("options")
        assert isinstance(opts, list) and len(opts) == 4
    if qtype == "true_false":
        ans = str(result.get("suggested_answer", "")).strip().lower()
        assert ans in {"true", "false"}
    if qtype == "commands":
        cmd = result.get("suggested_answer")
        assert isinstance(cmd, str) and cmd.strip()
    if qtype == "manifests":
        yml = result.get("suggested_answer")
        assert isinstance(yml, str) and yml.strip()
        obj = yaml.safe_load(yml)
        assert isinstance(obj, (dict, list))
        if isinstance(obj, dict):
            assert "apiVersion" in obj and "kind" in obj
"""


def main():
    out = Path("tests/test_ai_generation_matrix.py")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.format(subjects=repr(SUBJECTS)))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

