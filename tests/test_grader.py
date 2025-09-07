import pytest
import json
import yaml as yaml_lib
from kubelingo import grader

StaticValidator = grader.StaticValidator
AIEvaluator = grader.AIEvaluator
StaticValidationResult = grader.StaticValidationResult
AIEvaluationResult = grader.AIEvaluationResult

def test_validate_yaml_syntax_valid():
    validator = StaticValidator()
    ok, err = validator.validate_yaml_syntax("apiVersion: v1\nkind: Pod\n")
    assert ok is True
    assert err is None

def test_validate_yaml_syntax_invalid():
    validator = StaticValidator()
    # Use malformed YAML that should raise a parsing error
    ok, err = validator.validate_yaml_syntax("apiVersion: [v1, v2")
    assert ok is False
    assert isinstance(err, str)

def test_run_tool_unknown_returns_error_result():
    validator = StaticValidator()
    result = validator.run_tool("unknown_tool", "dummy")
    assert isinstance(result, StaticValidationResult)
    assert result.tool == "unknown_tool"
    assert result.passed is False
    assert result.score == 0
    assert any("Unknown tool" in issue for issue in result.issues)

def test_parse_ai_response_with_code_block():
    ai_eval = AIEvaluator(api_key="dummy", model="gpt-4", api_url="http://localhost")
    # Simulate AI response with code block
    response_text = "```json\n" + json.dumps({
        "score": 75,
        "explanation": "Detailed reasoning",
        "issues": ["issue1"],
        "suggestions": ["suggestion1"],
        "rewritten_manifest": None,
        "confidence": 0.85
    }) + "\n```"
    res = ai_eval._parse_ai_response(response_text)
    assert isinstance(res, AIEvaluationResult)
    assert res.score == 75
    assert "Detailed reasoning" in res.explanation
    assert res.issues == ["issue1"]
    assert res.suggestions == ["suggestion1"]
    assert res.rewritten_manifest is None
    assert abs(res.confidence - 0.85) < 1e-6