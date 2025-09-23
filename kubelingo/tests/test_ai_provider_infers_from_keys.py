import os


def test_infer_provider_from_keys_when_unset(monkeypatch, capsys):
    # Simulate unset provider
    monkeypatch.delenv('KUBELINGO_LLM_PROVIDER', raising=False)
    # Provide only an OpenAI key; enable offline key acceptance
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-12345678901234567890')
    monkeypatch.setenv('KUBELINGO_ASSUME_KEYS_VALID', 'true')

    from kubelingo.kubelingo import check_ai_ready_for_generation

    ok, msg = check_ai_ready_for_generation(print_warnings=True)
    out = capsys.readouterr().out

    assert ok is True
    assert msg == ''
    assert 'No AI provider configured' not in out

