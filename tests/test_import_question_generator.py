import importlib

def test_import_question_generator():
    """Ensure the kubelingo.question_generator module imports without syntax errors."""
    module = importlib.import_module("kubelingo.question_generator")
    assert hasattr(module, "QuestionGenerator"), "QuestionGenerator class should be defined in the module"