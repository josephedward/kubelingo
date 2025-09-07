import pytest
from unittest.mock import patch, MagicMock
from cli import static_quiz, generate_command, answer_question, generate_trivia, generate_ai_question_flow, main
import os
import shutil

@pytest.fixture
def setup_questions():
    os.makedirs("questions/uncategorized", exist_ok=True)
    with open("questions/uncategorized/test_question.json", "w") as f:
        f.write('{"id": "123", "question": "Test question", "suggestions": "test answer"}')
    yield
    shutil.rmtree("questions")

def test_static_quiz_shows_post_answer_menu(setup_questions):
    with patch('cli.inquirer.text') as mock_text, \
         patch('cli.inquirer.select') as mock_select, \
         patch('cli.print_post_answer_menu') as mock_print_post_answer_menu:
        mock_text.return_value.execute.return_value = "test answer"
        mock_select.return_value.execute.return_value = "again"
        
        static_quiz()
        
        mock_print_post_answer_menu.assert_called_once()

def test_generate_command_shows_post_answer_menu():
    with patch('cli.inquirer.select') as mock_select, \
         patch('cli.inquirer.text') as mock_text, \
         patch('cli.print_post_answer_menu') as mock_print_post_answer_menu, \
         patch('question_generator.QuestionGenerator.generate_question') as mock_generate_question:
        
        mock_select.return_value.execute.side_effect = ["pods", "again"]
        mock_generate_question.return_value = {
            "id": "123",
            "topic": "pods",
            "question": "Create a pod",
            "context_variables": {
                "pod_name": "test-pod",
                "image": "nginx"
            }
        }
        mock_text.return_value.execute.return_value = "kubectl run test-pod --image=nginx"
        
        generate_command()
        
        mock_print_post_answer_menu.assert_called()

def test_answer_question_shows_post_answer_menu():
    with patch('cli.inquirer.select') as mock_select, \
         patch('cli.inquirer.text') as mock_text, \
         patch('cli.print_post_answer_menu') as mock_print_post_answer_menu, \
         patch('k8s_manifest_generator.ManifestGenerator.grade_manifest') as mock_grade_manifest, \
         patch('question_generator.QuestionGenerator.generate_question') as mock_generate_question, \
         patch('cli._open_manifest_editor') as mock_open_manifest_editor:
        
        mock_select.return_value.execute.side_effect = ["pods", "again"]
        mock_generate_question.return_value = {
            "id": "123",
            "topic": "pods",
            "question": "Create a pod",
            "context_variables": {
                "pod_name": "test-pod",
                "image": "nginx"
            }
        }
        mock_text.return_value.execute.return_value = "vim"
        mock_open_manifest_editor.return_value = "apiVersion: v1"
        mock_grade_manifest.return_value = {"grade": "100/100"}
        
        answer_question()
        
        mock_print_post_answer_menu.assert_called_once()

def test_generate_trivia_shows_post_answer_menu():
    with patch('cli.inquirer.select') as mock_select, \
         patch('cli.inquirer.text') as mock_text, \
         patch('cli.print_post_answer_menu') as mock_print_post_answer_menu, \
         patch('cli.ai_chat') as mock_ai_chat:
        
        mock_select.return_value.execute.side_effect = ["pods", "again"]
        mock_ai_chat.return_value = '{"type": "tf", "question": "Is the sky blue?", "answer": "true"}'
        mock_text.return_value.execute.return_value = "true"
        
        generate_trivia()
        
        mock_print_post_answer_menu.assert_called()

def test_generate_ai_question_flow_shows_post_answer_menu():
    with patch('cli.inquirer.text') as mock_text, \
         patch('cli.print_menu') as mock_print_menu, \
         patch('cli.ai_chat') as mock_ai_chat, \
         patch('cli.inquirer.select') as mock_select:
        
        mock_ai_chat.return_value = '{"id": "456", "topic": "services", "question": "Create a service"}'
        mock_text.return_value.execute.return_value = "s"
        mock_select.return_value.execute.return_value = "again"
        
        generate_ai_question_flow()
        
        mock_print_menu.assert_any_call("post_answer")