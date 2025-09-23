import os
from unittest.mock import patch


def test_no_false_provider_warning_when_provider_configured_and_key_present(capsys, monkeypatch):
    # Ensure offline key checks treat provided keys as valid
    monkeypatch.setenv('KUBELINGO_ASSUME_KEYS_VALID', 'true')
    # Configure provider and a plausible key value
    monkeypatch.setenv('KUBELINGO_LLM_PROVIDER', 'openai')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-12345678901234567890')

    # Import after env is set so code reads fresh values
    from kubelingo.kubelingo import check_ai_ready_for_generation

    ok, msg = check_ai_ready_for_generation(print_warnings=True)
    captured = capsys.readouterr()

    # Should not warn about provider being unconfigured
    assert ok is True
    assert 'No AI provider configured' not in captured.out
    assert msg == ''

