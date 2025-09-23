import pytest
import cli
from InquirerPy import inquirer


class FakeAnswer:
    """Mimics InquirerPy answer object for testing."""
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


def test_generate_command_secrets_tls_suggestion(monkeypatch, capsys):
    """Test that generate_command suggests a TLS secret command for TLS Secret questions."""
    # Monkeypatch QuestionGenerator to return a TLS Secret question
    class DummyGen:
        def generate_question(self, topic, include_context=True):
            return {
                'id': 'test-tls',
                'topic': topic,
                'question': 'Use a TLS Secret to secure an Ingress resource',
                'documentation_link': None,
                'context_variables': {'secret_name': 'my-tls'}
            }
    monkeypatch.setattr(cli, 'QuestionGenerator', lambda: DummyGen())
    # Monkeypatch inquirer.text to immediately quit the command prompt
    texts = ['s', 'quit']
    monkeypatch.setattr(inquirer, 'text', lambda message=None, **kwargs: FakeAnswer(texts.pop(0)))
    # Execute generate_command for 'secrets' topic
    cli.generate_command(topic='secrets')
    # Capture output
    out = capsys.readouterr().out
    # Assert the suggested TLS Secret command is present
    assert 'Suggested Command:' in out
    assert 'kubectl create secret tls my-tls --cert=path/to/tls.crt --key=path/to/tls.key' in out

def test_generate_command_secrets_generic_literal_suggestion(monkeypatch, capsys):
    """Test that generate_command suggests a generic secret command with literals for username/password."""
    # Monkeypatch QuestionGenerator to return a generic Secret question
    class DummyGenLiteral:
        def generate_question(self, topic, include_context=True):
            return {
                'id': 'test-gen-literal',
                'topic': topic,
                'question': "Create a Secret named 'my-secret' with username 'admin' and password 's3cr3t'",
                'documentation_link': None,
                'context_variables': {
                    'secret_name': 'my-secret',
                    'secret_username': 'admin',
                    'secret_password': 's3cr3t'
                }
            }
    monkeypatch.setattr(cli, 'QuestionGenerator', lambda: DummyGenLiteral())
    # Monkeypatch inquirer.text to immediately quit
    texts = ['s', 'quit']
    monkeypatch.setattr(inquirer, 'text', lambda message=None, **kwargs: FakeAnswer(texts.pop(0)))
    # Execute generate_command for 'secrets' topic
    cli.generate_command(topic='secrets')
    # Capture output
    out = capsys.readouterr().out
    # Assert the suggested generic Secret command is present with username/password literals
    assert 'Suggested Command:' in out
    assert '--from-literal=username=admin' in out
    assert '--from-literal=password=s3cr3t' in out