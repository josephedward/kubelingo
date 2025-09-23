import sys
import pytest

from k8s_manifest_generator import main, ManifestGenerator


def test_two_step_question_mode(monkeypatch, capsys):
    # Prepare stub outputs for two AI calls: manifest then question
    stub_manifest = (
        "apiVersion: v1\n"
        "kind: Pod\n"
        "metadata:\n"
        "  name: stub-pod\n"
    )
    stub_question = (
        "Write a Pod manifest named stub-pod with apiVersion v1, kind Pod, "
        "metadata labels, and default spec settings."
    )

    calls = iter([stub_manifest, stub_question])

    def fake_generate_with_openai(self, prompt):
        try:
            return next(calls)
        except StopIteration:
            pytest.skip("No more stub AI responses")

    # Monkey-patch the AI generation method
    monkeypatch.setattr(ManifestGenerator, "generate_with_openai", fake_generate_with_openai)
    # Simulate CLI arguments
    monkeypatch.setattr(sys, "argv", ["prog", "--mode", "question", "--topic", "pods"]);

    # Run main and capture output
    main()
    captured = capsys.readouterr()
    out = captured.out

    # Validate the two-step process outputs
    assert "=== Two-Step AI Manifest Question Generation ===" in out
    assert "Generated Manifest:" in out
    assert stub_manifest in out
    assert "Generated Question:" in out
    assert stub_question in out
    # Ensure all manifest values appear in the generated question
    import yaml
    data = yaml.safe_load(stub_manifest)
    expected_vals = [data.get('apiVersion'), data.get('kind')]
    # metadata may be nested
    metadata = data.get('metadata', {})
    if isinstance(metadata, dict) and 'name' in metadata:
        expected_vals.append(metadata['name'])
    for val in expected_vals:
        assert str(val) in out