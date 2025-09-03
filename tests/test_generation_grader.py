import pytest
from kubelingo.generation.grader import KubernetesGrader, GraderType

def test_grade_invalid_yaml():
    grader = KubernetesGrader(grading_mode=GraderType.STATIC_ONLY)
    # Invalid YAML should yield zero score and 'F' grade
    # Use a manifest with unbalanced brackets for syntax error
    invalid_yaml = "key: [unclosed"
    result = grader.grade(invalid_yaml, question="q", goal="g", static_tools=[])
    assert result.overall_score == 0
    assert result.final_grade == "F"
    assert "YAML syntax error" in result.summary

def test_grade_empty_manifest_static_only():
    # Valid minimal YAML but no static tools
    minimal_yaml = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod"
    grader = KubernetesGrader(grading_mode=GraderType.STATIC_ONLY)
    result = grader.grade(minimal_yaml, question="Create pod", goal="deploy pod", static_tools=[])
    # No static tools means no validation, score defaults to 0
    assert result.overall_score == 0
    assert result.final_grade == "F"
    # Summary should reflect overall score
    assert result.summary.startswith("Overall Score: 0")