import os
from types import SimpleNamespace


def _setup_env(monkeypatch):
    # Ensure offline heuristic treats provided keys as valid
    monkeypatch.setenv('KUBELINGO_ASSUME_KEYS_VALID', 'true')
    # No explicit provider in env for these tests
    monkeypatch.delenv('KUBELINGO_LLM_PROVIDER', raising=False)
    # Provide a plausible OpenAI key so status check passes
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-12345678901234567890')


def test_current_provider_reads_package_env_when_no_env_var(capsys, monkeypatch):
    _setup_env(monkeypatch)

    # Import module under test
    import kubelingo.kubelingo as app

    pkg_dir = os.path.dirname(app.__file__)
    pkg_env = os.path.join(pkg_dir, '.env')
    project_root = os.path.abspath(os.path.join(pkg_dir, os.pardir))
    root_env = os.path.join(project_root, '.env')

    # Patch dotenv_values to return provider only for package-level .env
    def fake_dotenv_values(path=None):
        if path == pkg_env:
            return {'KUBELINGO_LLM_PROVIDER': 'openai'}
        # Simulate no provider elsewhere
        return {}

    # Patch exists so code believes only package-level .env exists
    real_exists = app.os.path.exists

    def fake_exists(p):
        if p == pkg_env:
            return True
        if p == root_env:
            return False
        return real_exists(p)

    monkeypatch.setattr(app, 'dotenv_values', fake_dotenv_values)
    monkeypatch.setattr(app.os.path, 'exists', fake_exists)

    ok, msg = app.check_ai_ready_for_generation(print_warnings=True)
    captured = capsys.readouterr()
    assert ok is True
    assert msg == ''
    assert 'No AI provider configured' not in captured.out


def test_current_provider_reads_root_env_when_no_env_var(capsys, monkeypatch):
    _setup_env(monkeypatch)

    import kubelingo.kubelingo as app

    pkg_dir = os.path.dirname(app.__file__)
    pkg_env = os.path.join(pkg_dir, '.env')
    project_root = os.path.abspath(os.path.join(pkg_dir, os.pardir))
    root_env = os.path.join(project_root, '.env')

    # Patch dotenv_values to return provider only for root .env
    def fake_dotenv_values(path=None):
        if path == root_env:
            return {'KUBELINGO_LLM_PROVIDER': 'openai'}
        return {}

    real_exists = app.os.path.exists

    def fake_exists(p):
        if p == root_env:
            return True
        if p == pkg_env:
            return False
        return real_exists(p)

    monkeypatch.setattr(app, 'dotenv_values', fake_dotenv_values)
    monkeypatch.setattr(app.os.path, 'exists', fake_exists)

    ok, msg = app.check_ai_ready_for_generation(print_warnings=True)
    captured = capsys.readouterr()
    assert ok is True
    assert msg == ''
    assert 'No AI provider configured' not in captured.out

