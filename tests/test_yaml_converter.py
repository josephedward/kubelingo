import sys
import json
import yaml
import pytest
from pathlib import Path

# Ensure the qgen+grader directory is on the import path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts' / 'qgen+grader_090125'))

from yaml_converter import YAMLConverter

def test_convert_suggestion_dict_and_list():
    conv = YAMLConverter()
    suggestion_dict = {'a': 1}
    result = conv.convert_suggestion_to_yaml(suggestion_dict)
    assert isinstance(result, list)
    assert result == [suggestion_dict]
    suggestion_list = [{'a': 2}, {'b': 3}]
    result2 = conv.convert_suggestion_to_yaml(suggestion_list)
    assert isinstance(result2, list)
    assert result2 == suggestion_list

def test_convert_suggestion_kubectl_command():
    conv = YAMLConverter()
    suggestion = 'kubectl apply -f file.yaml'
    result = conv.convert_suggestion_to_yaml(suggestion)
    assert result == suggestion

def test_convert_suggestion_yaml_string():
    conv = YAMLConverter()
    yaml_str = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\n"
    result = conv.convert_suggestion_to_yaml(yaml_str)
    assert isinstance(result, list)
    assert result[0]['kind'] == 'Pod'

def test_convert_questions_file_and_validate(tmp_path):
    conv = YAMLConverter()
    data = {
        'questions': [
            {'question': 'Q1', 'suggestion': "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test"}
        ]
    }
    input_file = tmp_path / 'questions.json'
    output_file = tmp_path / 'questions_out.yaml'
    input_file.write_text(json.dumps(data))
    stats = conv.convert_questions_file(str(input_file), str(output_file))
    assert stats['total_questions'] == 1
    assert stats['successful_conversions'] == 1
    loaded = yaml.safe_load(output_file.read_text())
    assert 'questions' in loaded
    suggestion = loaded['questions'][0]['suggestion']
    assert isinstance(suggestion, list)
    assert suggestion[0]['kind'] == 'Pod'

def test_validate_yaml_file(tmp_path):
    conv = YAMLConverter()
    questions = {
        'questions': [
            {'question': 'Q1', 'suggestion': 'kubectl get pods'}
        ]
    }
    file_path = tmp_path / 'q.yaml'
    file_path.write_text(yaml.dump(questions))
    results = conv.validate_yaml_file(str(file_path))
    assert results['valid']
    assert results['question_count'] == 1
    assert results['command_count'] == 1