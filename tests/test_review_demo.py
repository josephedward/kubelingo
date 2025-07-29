import json
from kubelingo.modules.kubernetes.session import load_questions, mark_question_for_review, unmark_question_for_review

data_file = 'testdata.json'
# Initialize test data
data = [{
    'category': 'TestCat',
    'prompts': [
        {'prompt': 'foo', 'response': 'foo', 'type': 'command'},
        {'prompt': 'bar', 'response': 'bar', 'type': 'command', 'review': True}
    ]
}]
with open(data_file, 'w') as f:
    json.dump(data, f, indent=2)
print('Initial data:', json.load(open(data_file)))
# Mark 'foo' for review
mark_question_for_review(data_file, 'TestCat', 'foo')
data1 = json.load(open(data_file))
print("After marking 'foo':", data1)
# Load questions and list flagged
qs = load_questions(data_file)
flagged = [q['prompt'] for q in qs if q.get('review')]
print('Flagged prompts:', flagged)
# Unmark 'bar'
unmark_question_for_review(data_file, 'TestCat', 'bar')
data2 = json.load(open(data_file))
print("After unmarking 'bar':", data2)
# Final flagged prompts
qs2 = load_questions(data_file)
flagged2 = [q['prompt'] for q in qs2 if q.get('review')]
print('Final flagged prompts:', flagged2)
