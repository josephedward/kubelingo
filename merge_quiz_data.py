#!/usr/bin/env python3
"""Merge CKAD quiz JSON data files into a single deduplicated JSON file."""
import json
from collections import OrderedDict, defaultdict

def main():
    input_files = ['ckad_quiz_data.json', 'ckad_quiz_data_with_explanations.json']
    merged = OrderedDict()

    for fname in input_files:
        try:
            with open(fname, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Warning: {fname} not found, skipping.")
            continue
        except json.JSONDecodeError as e:
            print(f"Error parsing {fname}: {e}")
            continue
        for section in data:
            category = section.get('category', '')
            for item in section.get('prompts', []):
                prompt = item.get('prompt', '').strip()
                response = item.get('response', '').strip()
                explanation = item.get('explanation', '').strip()
                # Fix prompt detail for known ambiguous question
                if prompt == "Create a pod in the 'development' namespace":
                    # Prompt should include pod name and image for clarity
                    prompt = "Create a pod named nginx using the nginx image in the 'development' namespace"
                key = (prompt, response)
                if key not in merged:
                    merged[key] = {
                        'category': category,
                        'prompt': prompt,
                        'response': response,
                        'explanation': explanation
                    }
                else:
                    # Merge in any missing explanation
                    if not merged[key]['explanation'] and explanation:
                        merged[key]['explanation'] = explanation

    # Group by category
    grouped = defaultdict(list)
    for entry in merged.values():
        grouped[entry['category']].append({
            'prompt': entry['prompt'],
            'response': entry['response'],
            'explanation': entry.get('explanation', '')
        })

    # Build final list
    output = []
    for category in sorted(grouped):
        output.append({
            'category': category,
            'prompts': grouped[category]
        })

    # Write combined JSON
    out_path = 'ckad_quiz_data_combined.json'
    with open(out_path, 'w') as out_f:
        json.dump(output, out_f, indent=2)
    total = sum(len(v) for v in grouped.values())
    print(f"Wrote {out_path} containing {total} unique questions in {len(grouped)} categories.")

if __name__ == '__main__':
    main()