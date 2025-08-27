# This module will contain functions for generating new questions.

import os
import random
import yaml
import requests
import sys
from thefuzz import fuzz
from colorama import Fore, Style

# Import necessary functions/variables from kubelingo.py
from kubelingo.kubelingo import _get_llm_model, QUESTIONS_DIR, load_questions, get_normalized_question_text, Fore, Style

def generate_more_questions(topic, question):
    """Generates more questions based on an existing one."""
    llm_type, model = _get_llm_model()
    if not model:
        print("\nINFO: Set GEMINI_API_KEY or OPENAI_API_KEY environment variables to generate new questions.")
        return None

    print("\nGenerating a new question... this might take a moment.")
    try:
        question_type = random.choice(['command', 'manifest'])
        
        # Get all existing questions for the topic to include in the prompt for uniqueness
        all_existing_questions = load_questions(topic)
        existing_questions_list = all_existing_questions.get('questions', []) if all_existing_questions else []
        
        existing_questions_yaml = ""
        if existing_questions_list:
            existing_questions_yaml = "\n        Existing Questions (DO NOT copy these semantically or literally):\n        ---"
            for eq in existing_questions_list:
                existing_questions_yaml += f"        - question: {eq.get('question', '')}\n"
                if eq.get('solution'):
                    existing_questions_yaml += f"          solution: {str(eq.get('solution', ''))[:50]}...\n" # Truncate solution for prompt
                existing_questions_yaml += "\n"
            existing_questions_yaml += "        ---\n"



        prompt = f'''
        You are a Kubernetes expert creating questions for a CKAD study guide.
        Based on the following example question about '{topic}', please generate one new, distinct but related question.
        The new question MUST be unique and not a semantic or literal copy of any existing questions provided.

        Example Question:
        ---\n{yaml.safe_dump({'questions': [question]})}        ---\n
        {existing_questions_yaml}
        Your new question should be a {question_type}-based question.
        - If it is a 'command' question, the suggestion should be a single or multi-line shell command (e.g., kubectl).
        - If it is a 'manifest' question, the suggestion should be a complete YAML manifest and the question should be phrased to ask for a manifest.

        The new question should be in the same topic area but test a slightly different aspect or use different parameters.
        Provide the output in valid YAML format, as a single item in a 'questions' list.
        The output must include a 'source' field with a valid URL pointing to the official Kubernetes documentation or a highly reputable source that justifies the answer.
        The solution must be correct and working.
        If a 'starter_manifest' is provided, it must use the literal block scalar style (e.g., 'starter_manifest: |').
        Also, include a brief 'rationale' field explaining why this question is relevant for CKAD and what it tests.

        Example for a manifest question:
        questions:
          - question: "Create a manifest for a Pod named 'new-pod'"
            solution: |
              apiVersion: v1
              kind: Pod
              metadata:
                name: new-pod
            source: "https://kubernetes.io/docs/concepts/workloads/pods/"
            rationale: "Tests basic Pod creation and YAML syntax."

        Example for a command question:
        questions:
          - question: "Create a pod named 'new-pod' imperatively..."
            solution: "kubectl run new-pod --image=nginx"
            source: "https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#run"
            rationale: "Tests imperative command usage for Pod creation."
        '''
        if llm_type == "gemini":
            response = model.generate_content(prompt)
        elif llm_type == "openai" or llm_type == "openrouter":
            response = model.chat.completions.create(
                model="gpt-3.5-turbo", # Or another suitable model
                messages=[
                    {"role": "system", "content": "You are a Kubernetes expert creating questions for a CKAD study guide."},
                    {"role": "user", "content": prompt}
                ]
            )
            response.text = response.choices[0].message.content # Normalize response for consistent parsing

        # Clean the response to only get the YAML part
        cleaned_response = response.text.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]

        try:
            new_question_data = yaml.safe_load(cleaned_response)
        except yaml.YAMLError:
            print("\nAI failed to generate a valid question (invalid YAML). Please try again.")
            return None
        
        if new_question_data and 'questions' in new_question_data and new_question_data['questions']:
            new_q = new_question_data['questions'][0]

            # Uniqueness check
            normalized_new_q_text = get_normalized_question_text(new_q)
            for eq in existing_questions_list:
                if get_normalized_question_text(eq) == normalized_new_q_text:
                    print(f"{Fore.YELLOW}\nGenerated question is a duplicate. Retrying...{Style.RESET_ALL}")
                    return None # Indicate failure to generate a unique question

            # Normalize generated question: convert 'solution' to 'suggestion' list and clean whitespace
            if 'suggestion' in new_q:
                raw_sug = new_q.pop('suggestion')
                suggestion_list = raw_sug if isinstance(raw_sug, list) else [raw_sug]
            elif 'solution' in new_q:
                raw_sol = new_q.pop('solution')
                suggestion_list = [raw_sol]
            else:
                suggestion_list = []
            cleaned_suggestion = []
            for item in suggestion_list:
                if isinstance(item, str):
                    cleaned_suggestion.append(item.strip())
                else:
                    cleaned_suggestion.append(item)
            if cleaned_suggestion:
                new_q['suggestion'] = cleaned_suggestion
            
            # Ensure 'source' field exists
            if not new_q.get('source'):
                print(f"{Fore.YELLOW}\nGenerated question is missing a 'source' field. Attempting to find one...{Style.RESET_ALL}")
                # This is where _find_and_assign_source would be called later
                # For now, we'll just return None to indicate a problem
                return None

            print("\nNew question generated!")
            return new_q
        else:
            print("\nAI failed to generate a valid question. Please try again.")
            return None
    except Exception as e:
        print(f"\nError generating question: {e}")
        return None