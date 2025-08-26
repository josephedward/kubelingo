import os
import yaml
import pytest
from kubelingo import kubelingo
from unittest.mock import patch

USER_DATA_DIR = "user_data"
QUESTIONS_DIR = "questions"

@pytest.fixture
def setup_user_data_dir(tmp_path):
    """Fixture to set up a temporary user data directory."""
    original_user_data_dir = kubelingo.USER_DATA_DIR
    kubelingo.USER_DATA_DIR = str(tmp_path)
    yield
    kubelingo.USER_DATA_DIR = original_user_data_dir

@pytest.fixture
def setup_questions_dir(tmp_path):
    """Fixture to set up a temporary questions directory."""
    original_questions_dir = kubelingo.QUESTIONS_DIR
    kubelingo.QUESTIONS_DIR = str(tmp_path)
    yield
    kubelingo.QUESTIONS_DIR = original_questions_dir

def test_instruction_update():
    """Test that instructions correctly ignore indentation styles and field order."""
    question_dict = {
        'question': 'Modify the manifest to mount a Secret named "secret2".',
        'solution': {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {'name': 'mypod'},
            'spec': {
                'containers': [{
                    'name': 'my-container',
                    'image': 'nginx',
                    'volumeMounts': [{'name': 'secret-volume', 'mountPath': '/tmp/secret2'}]
                }],
                'volumes': [{'name': 'secret-volume', 'secret': {'secretName': 'secret2'}}]
            }
        }
    }
    user_manifest = """
    apiVersion: v1
    kind: Pod
    metadata:
      name: mypod
    spec:
      containers:
      - name: my-container
        image: nginx
        volumeMounts:
        - mountPath: /tmp/secret2
          name: secret-volume
      volumes:
      - name: secret-volume
        secret:
          secretName: secret2
    """
    result = kubelingo.validate_manifest_with_llm(question_dict, user_manifest)
    assert result['correct'], "The manifest should be considered correct."

def test_create_issue_with_setup(setup_user_data_dir, setup_questions_dir):
    """Test that creating an issue saves the question and removes it from the topic file."""
    question_dict = {'question': 'Sample question', 'solution': 'Sample solution'}
    topic = 'sample_topic'
    issues_file = os.path.join(kubelingo.USER_DATA_DIR, 'issues.yaml')
    topic_file = os.path.join(kubelingo.QUESTIONS_DIR, f'{topic}.yaml')

    # Create a sample topic file
    with open(topic_file, 'w') as f:
        yaml.dump({'questions': [question_dict]}, f)

    with patch('builtins.input', return_value="This is a test issue."):
        kubelingo.create_issue(question_dict, topic)

    # Check that the issue was saved
    with open(issues_file, 'r') as f:
        issues = yaml.safe_load(f)
    assert any(q['question'] == 'Sample question' for q in issues), "The issue should be saved."

    # Check that the question was removed from the topic file
    with open(topic_file, 'r') as f:
        data = yaml.safe_load(f)
    assert not any(q['question'] == 'Sample question' for q in data['questions']), "The question should be removed from the topic file."

def test_generate_option_availability(setup_user_data_dir, setup_questions_dir):
    """Test that the 'generate' option is only available at 100% completion."""
    performance_data = {
        'sample_topic': {
            'correct_questions': ['sample question']
        }
    }
    question_dict = {'question': 'Sample question', 'solution': 'Sample solution'}
    topic_file = os.path.join(kubelingo.QUESTIONS_DIR, 'sample_topic.yaml')

    # Create a sample topic file
    with open(topic_file, 'w') as f:
        yaml.dump({'questions': [question_dict]}, f)

    selected_topic, num_to_study, questions_to_study = kubelingo.list_and_select_topic(performance_data)
    assert selected_topic == 'sample_topic', "The selected topic should be 'sample_topic'."
    assert num_to_study == 0, "The 'generate' option should be available when there are no questions left to study."
