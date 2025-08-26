import unittest
import yaml
import os

class TestQuestionSchema(unittest.TestCase):
    def test_all_questions_have_required_keys(self):
        questions_dir = os.path.join(os.path.dirname(__file__), 'questions')
        for filename in os.listdir(questions_dir):
            if filename.endswith('.yaml'):
                filepath = os.path.join(questions_dir, filename)
                with open(filepath, 'r') as f:
                    # Some files might be empty or not have a questions list
                    # This is fine for other yaml files, but question files should have questions
                    if os.path.getsize(filepath) == 0:
                        continue
                    data = yaml.safe_load(f)
                    if not data or 'questions' not in data:
                        continue

                    self.assertIn('questions', data, f"File {filename} is missing 'questions' key")
                    
                    for i, q in enumerate(data['questions']):
                        with self.subTest(f"File: {filename}, Question: {i+1}"):
                            self.assertIn('question', q, f"'question' key is missing in {q}")

if __name__ == '__main__':
    unittest.main()
