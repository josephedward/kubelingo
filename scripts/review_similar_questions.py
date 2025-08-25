import os
import yaml
import re
from glob import glob
from thefuzz import fuzz

# Function to normalize question text
def normalize_question_text(text):
    text = text.lower()  # Lowercase
    text = re.sub(r'[\W_]+', ' ', text)  # Remove punctuation and replace with space
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text

# Function to calculate question detail score
def get_question_detail_score(question):
    score = 0
    # Length of question text
    score += len(question.get('question', ''))
    # Presence of source URL
    if question.get('source'):
        score += 50 # Arbitrary bonus
    # Length/complexity of solution
    if 'solution' in question and isinstance(question['solution'], str):
        score += len(question['solution'])
    elif 'solutions' in question and isinstance(question['solutions'], list):
        for sol in question['solutions']:
            if isinstance(sol, str):
                score += len(sol) # Sum of lengths of all solutions
        score += 20 # Bonus for multiple solutions
    # Presence of starter_manifest
    if question.get('starter_manifest'):
        score += 100 # Significant bonus for manifest questions
    return score

# Main processing logic
all_questions = []
questions_dir = "/Users/user/Documents/GitHub/kubelingo/questions"
yaml_files = glob(os.path.join(questions_dir, "**", "*.yaml"), recursive=True)

for file_path in yaml_files:
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    
    if data and 'questions' in data:
        for idx, q in enumerate(data['questions']):
            if 'question' in q:
                all_questions.append({
                    'original_question': q,
                    'normalized_text': normalize_question_text(q['question']),
                    'file_path': file_path,
                    'index': idx,
                    'detail_score': get_question_detail_score(q)
                })

# Find similar questions
similarity_threshold = 85 # Adjust as needed
similar_groups = []
processed_indices = set()

for i, q1_info in enumerate(all_questions):
    if i in processed_indices:
        continue

    current_group = [q1_info]
    processed_indices.add(i)

    for j, q2_info in enumerate(all_questions):
        if i == j or j in processed_indices:
            continue
        
        similarity = fuzz.token_set_ratio(q1_info['normalized_text'], q2_info['normalized_text'])
        
        if similarity >= similarity_threshold:
            current_group.append(q2_info)
            processed_indices.add(j)
    
    if len(current_group) > 1:
        similar_groups.append(current_group)

# Report findings (non-interactive)
if not similar_groups:
    print("No significantly similar questions found.")
else:
    print(f"Found {len(similar_groups)} groups of similar questions.\n")
    for i, group in enumerate(similar_groups):
        print(f"--- Group {i+1} ---")
        # Sort by detail score to easily identify the most detailed one
        group_sorted_by_detail = sorted(group, key=lambda x: x['detail_score'], reverse=True)
        
        best_question = group_sorted_by_detail[0]
        questions_to_remove = group_sorted_by_detail[1:]

        print(f"  Suggested to keep (highest score):\n    File: {os.path.basename(best_question['file_path'])} | Question: {best_question['original_question']['question']}")
        
        if questions_to_remove:
            print("  Questions to consider removing:")
            for q_info in questions_to_remove:
                print(f"    File: {os.path.basename(q_info['file_path'])} | Question: {q_info['original_question']['question']}")
        else:
            print("  (No other questions to remove in this group)")
        print("\n")