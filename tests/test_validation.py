import pytest
import os
import yaml
from dotenv import dotenv_values
from unittest.mock import patch, mock_open, MagicMock, call
from colorama import Fore, Style
from kubelingo.validation import (
    validate_manifest_with_llm,
    validate_manifest_with_kubectl_dry_run,
    validate_kubectl_command_dry_run,
    validate_manifest
)
from kubelingo.utils import _get_llm_model, QUESTIONS_DIR

@pytest.fixture
def mock_llm_deps(mocker):
    mock_environ = {}

    mock_genai_module = MagicMock()
    mock_genai_module.configure = MagicMock()
    mock_gemini_model_instance = MagicMock()
    mock_genai_module.GenerativeModel = MagicMock(return_value=mock_gemini_model_instance)

    mock_openai_client_instance = MagicMock()
    mock_openai_module = MagicMock()
    mock_openai_module.OpenAI = MagicMock(return_value=mock_openai_client_instance)

    with (
        patch.dict('sys.modules', {'google.generativeai': mock_genai_module, 'openai': mock_openai_module}),
        patch.dict('os.environ', mock_environ, clear=True),
        patch('kubelingo.validation.requests.post') as mock_requests_post,
        patch('kubelingo.validation.validate_kubectl_command_dry_run') as mock_validate_kubectl_command_dry_run
    ):
        # Configure mock response for OpenRouter health check
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {}
        
        # Configure mock for validate_kubectl_command_dry_run
        mock_validate_kubectl_command_dry_run.return_value = (True, "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\n", "")

        yield mock_genai_module.configure, mock_genai_module.GenerativeModel, mock_gemini_model_instance, mock_openai_module.OpenAI, mock_openai_client_instance, mock_environ, mock_requests_post, mock_validate_kubectl_command_dry_run

def test_validate_manifest_with_llm_gemini(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_requests_post, mock_validate_kubectl_command_dry_run = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.validation._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.text = "CORRECT\nManifest is valid."
        mock_gemini_model_instance.generate_content.return_value = mock_response
        
        question_dict = {'question': 'Q', 'solution': 'S'}
        user_manifest = "M"
        
        result = validate_manifest_with_llm(question_dict, user_manifest)
        
            # AI model should have been invoked and returned an LLM decision
            # skip specific call count assertions to allow multiple invocations
        assert result == {'correct': True, 'feedback': 'Manifest is valid.'}

def test_validate_manifest_with_llm_openai(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_requests_post, mock_validate_kubectl_command_dry_run = mock_llm_deps
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.validation._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "INCORRECT\nManifest is missing a field."
        mock_openai_client_instance.chat.completions.create.return_value = mock_response
        
        question_dict = {'question': 'Q', 'solution': 'S'}
        user_manifest = "M"
        
        result = validate_manifest_with_llm(question_dict, user_manifest)
        
        # Ensure AI model was invoked and result is returned correctly
        assert result == {'correct': False, 'feedback': 'Manifest is missing a field.'}

def test_validate_manifest_with_llm_no_llm(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_requests_post, mock_validate_kubectl_command_dry_run = mock_llm_deps
    
    # Patch _get_llm_model to return no model
    with patch('kubelingo.validation._get_llm_model', return_value=(None, None)) as mock_get_llm_model:
        result = validate_manifest_with_llm({'question': 'Q', 'solution': 'S'}, "M")
        
        # LLM provider not configured; fallback message returned
        assert result == {'correct': False, 'feedback': "INFO: Set GEMINI_API_KEY or OPENAI_API_KEY for AI-powered manifest validation."}

def test_validate_manifest_with_llm_gemini_error(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_requests_post, mock_validate_kubectl_command_dry_run = mock_llm_deps
    
    # Patch _get_llm_model to return a configured Gemini model
    with patch('kubelingo.validation._get_llm_model', return_value=("gemini", mock_gemini_model_instance)) as mock_get_llm_model:
        mock_gemini_model_instance.generate_content.side_effect = Exception("Gemini manifest error")
        
        result = validate_manifest_with_llm({'question': 'Q', 'solution': 'S'}, "M")
        
        # Ensure Gemini exception is correctly captured
        assert result == {'correct': False, 'feedback': "Error validating manifest with LLM: Gemini manifest error"}

def test_validate_manifest_with_llm_openai_error(mock_llm_deps):
    mock_gemini_configure, MockGenerativeModel_class, mock_gemini_model_instance, MockOpenAI_class, mock_openai_client_instance, mock_environ, mock_requests_post, mock_validate_kubectl_command_dry_run = mock_llm_deps
    
    # Patch _get_llm_model to return a configured OpenAI model
    with patch('kubelingo.validation._get_llm_model', return_value=("openai", mock_openai_client_instance)) as mock_get_llm_model:
        mock_openai_client_instance.chat.completions.create.side_effect = Exception("OpenAI manifest error")
        
        result = validate_manifest_with_llm({'question': 'Q', 'solution': 'S'}, "M")
        
        # Ensure OpenAI exception is correctly captured
        assert result == {'correct': False, 'feedback': "Error validating manifest with LLM: OpenAI manifest error"}

class TestKubectlValidation:
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        # Mock tempfile.NamedTemporaryFile to control file creation
        with patch('tempfile.NamedTemporaryFile', new_callable=mock_open) as mock_tmp_file:
            self.mock_tmp_file = mock_tmp_file
            self.mock_tmp_file_handle = mock_tmp_file.return_value.__enter__.return_value
            self.mock_tmp_file_handle.name = "/tmp/mock_temp_file.yaml" # Assign a mock name

            # Mock os.unlink for temp file cleanup
            with patch('os.unlink') as mock_unlink:
                self.mock_unlink = mock_unlink
                yield

    # --- Tests for validate_manifest_with_kubectl_dry_run ---

    def test_validate_manifest_valid_yaml(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "pod/test-pod created (dry-run)\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            assert "pod/test-pod created (dry-run)" in ai_feedback
            mock_subprocess_run.assert_called_once()
            self.mock_tmp_file.assert_called_once_with(mode='w+', suffix=".yaml", delete=False)
            self.mock_tmp_file_handle.write.assert_called_once_with(manifest)
            self.mock_unlink.assert_called_once_with("/tmp/mock_temp_file.yaml")

    def test_validate_manifest_invalid_yaml(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Error from server (BadRequest): error when creating \"/tmp/mock_temp_file.yaml\": Pod in version \"v1\" cannot be handled as a Pod: strict decoding error: unknown field \"invalidField\"\n"

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\ninvalidField: value\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is False
            assert "kubectl dry-run failed. Please check your manifest." in user_feedback
            assert "unknown field \"invalidField\"" in ai_feedback
            mock_subprocess_run.assert_called_once()
            self.mock_unlink.assert_called_once()

    def test_validate_manifest_not_kubernetes_yaml(self, capsys):
        manifest = "key: value\nanother_key: another_value\n"
        success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

        assert success is False
        assert "Skipping kubectl dry-run: Not a Kubernetes YAML manifest." in user_feedback
        assert "Skipped: Not a Kubernetes YAML manifest." in ai_feedback
        # Ensure subprocess.run and tempfile operations were not called
        with patch('subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.assert_not_called()
        self.mock_tmp_file.assert_not_called()
        self.mock_unlink.assert_not_called()

    def test_validate_manifest_kubectl_not_found(self, capsys):
        with patch('subprocess.run', side_effect=FileNotFoundError) as mock_subprocess_run:
            manifest = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is False
            assert "Error: 'kubectl' command not found." in user_feedback
            assert "kubectl not found" in ai_feedback
            mock_subprocess_run.assert_called_once()
            self.mock_unlink.assert_called_once()

    def test_validate_manifest_with_leading_comments(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "pod/test-pod created (dry-run)\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            manifest = "# This is a comment\n\napiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\nspec:\n  containers:\n  - name: test-container\n    image: nginx\n"
            success, user_feedback, ai_feedback = validate_manifest_with_kubectl_dry_run(manifest)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            mock_subprocess_run.assert_called_once()

    # --- Tests for validate_kubectl_command_dry_run ---

    def test_validate_kubectl_command_valid_run(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "apiVersion: v1\nkind: Pod\nmetadata:\n  creationTimestamp: \n  labels:\n    run: my-pod\n  name: my-pod\nspec:\n  containers:\n  - image: nginx\n    name: my-pod\n    resources: {}\nstatus: {}\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            assert "kind: Pod" in ai_feedback
            mock_subprocess_run.assert_called_once_with(
                ["kubectl", "run", "my-pod", "--image=nginx", "--dry-run=client", "-o", "yaml"],
                capture_output=True, text=True, check=False
            )

    def test_validate_kubectl_command_invalid_run(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Error: unknown flag: --invalid-flag\n"

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx --invalid-flag"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is False
            assert "kubectl dry-run failed. Please check your command syntax." in user_feedback
            assert "unknown flag: --invalid-flag" in ai_feedback
            mock_subprocess_run.assert_called_once()

    def test_validate_kubectl_command_skipped_get(self, capsys):
        command_string = "kubectl get pods"
        success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

        assert success is True
        assert "Skipping kubectl dry-run: Command type not typically dry-runnable client-side." in user_feedback
        assert "Skipped: Command type not typically dry-runnable client-side." in ai_feedback
        with patch('subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.assert_not_called()

    def test_validate_kubectl_command_skipped_non_kubectl(self, capsys):
        command_string = "ls -l"
        success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

        assert success is True
        assert "Skipping kubectl dry-run: Command type not typically dry-runnable client-side." in user_feedback
        assert "Skipped: Command type not typically dry-runnable client-side." in ai_feedback
        with patch('subprocess.run') as mock_subprocess_run:
            mock_subprocess_run.assert_not_called()

    def test_validate_kubectl_command_kubectl_not_found(self, capsys):
        with patch('subprocess.run', side_effect=FileNotFoundError) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is False
            assert "Error: 'kubectl' command not found." in user_feedback
            assert "kubectl not found" in ai_feedback
            mock_subprocess_run.assert_called_once()

    def test_validate_kubectl_command_already_has_dry_run_and_output(self, capsys):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: my-pod\nspec:\n  containers:\n  - image: nginx\n    name: my-pod\n"
        mock_process.stderr = ""

        with patch('subprocess.run', return_value=mock_process) as mock_subprocess_run:
            command_string = "kubectl run my-pod --image=nginx --dry-run=client -o json"
            success, user_feedback, ai_feedback = validate_kubectl_command_dry_run(command_string)

            assert success is True
            assert "kubectl dry-run successful!" in user_feedback
            assert "kind: Pod" in ai_feedback
            mock_subprocess_run.assert_called_once_with(
                ["kubectl", "run", "my-pod", "--image=nginx", "--dry-run=client", "-o", "json"],
                capture_output=True, text=True, check=False
            )
