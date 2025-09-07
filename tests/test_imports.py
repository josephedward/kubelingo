"""
Sanity tests to ensure key modules import without syntax errors.
"""
import pytest

def test_import_core_modules():
    try:
        import kubelingo.cli  # CLI entrypoint
        import kubelingo.question_generator  # Question generator
        import kubelingo.k8s_manifest_generator  # Manifest generator
    except Exception as e:
        pytest.fail(f"Importing core module failed with error: {e}")