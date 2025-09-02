#!/usr/bin/env python3
"""
YAML Conversion Utility for Quiz App
===================================

Converts between different formats:
1. JSON with escaped YAML strings -> Proper YAML structure
2. Validates and fixes common escape sequence issues
3. Handles both single manifests and arrays of manifests
"""

import json
import yaml
import argparse
import re
from pathlib import Path
from typing import Dict, List, Any, Union

class YAMLConverter:
    """Handles conversion between different YAML/JSON formats"""

    def __init__(self):
        self.conversion_stats = {
            'total_questions': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'already_proper_format': 0
        }

    def fix_escaped_yaml(self, escaped_string: str) -> str:
        """Fix common escape sequence issues in YAML strings"""
        # Handle common escape sequences
        fixed = escaped_string.replace('\\n', '\n')  # Double-escaped newlines
        fixed = fixed.replace('\n', '\n')            # Normal newlines
        fixed = fixed.replace('\\"', '"')             # Escaped quotes
        fixed = fixed.replace('\\t', '\t')          # Double-escaped tabs
        fixed = fixed.replace('\t', '  ')             # Convert tabs to spaces

        # Remove extra escaping that might occur
        fixed = re.sub(r'\\(.)', r'\\1', fixed)    # Remove double backslashes

        return fixed

    def convert_suggestion_to_yaml(self, suggestion: Union[str, List, Dict]) -> Union[List[Dict], str]:
        """Convert various suggestion formats to proper YAML structure"""

        # Already proper format (list of dicts or single dict)
        if isinstance(suggestion, (list, dict)):
            self.conversion_stats['already_proper_format'] += 1
            return suggestion if isinstance(suggestion, list) else [suggestion]

        # String format - needs parsing
        if isinstance(suggestion, str):
            # Check if it's a kubectl command (no YAML conversion needed)
            if suggestion.strip().startswith('kubectl'):
                return suggestion

            try:
                # Fix escape sequences
                fixed_yaml = self.fix_escaped_yaml(suggestion)

                # Try to parse as YAML
                parsed = yaml.safe_load(fixed_yaml)

                if parsed is None:
                    self.conversion_stats['failed_conversions'] += 1
                    return suggestion  # Return original if parsing fails

                # Ensure it's a list for consistency
                result = [parsed] if isinstance(parsed, dict) else parsed
                self.conversion_stats['successful_conversions'] += 1
                return result

            except yaml.YAMLError as e:
                print(f"YAML parsing failed: {e}")
                self.conversion_stats['failed_conversions'] += 1
                return suggestion  # Return original string if parsing fails

        # Unknown format
        self.conversion_stats['failed_conversions'] += 1
        return suggestion

    def convert_questions_file(self, input_file: str, output_file: str) -> Dict[str, int]:
        """Convert a questions file from escaped format to proper YAML"""

        # Reset stats
        self.conversion_stats = {k: 0 for k in self.conversion_stats}

        # Load input file
        with open(input_file, 'r') as f:
            if input_file.endswith('.json'):
                data = json.load(f)
            else:
                data = yaml.safe_load(f)

        if 'questions' not in data:
            raise ValueError("Input file must contain a 'questions' key")

        self.conversion_stats['total_questions'] = len(data['questions'])

        # Convert each question
        converted_questions = []
        for question in data['questions']:
            converted_question = question.copy()

            if 'suggestion' in question:
                converted_question['suggestion'] = self.convert_suggestion_to_yaml(question['suggestion'])

            converted_questions.append(converted_question)

        # Save converted data
        converted_data = {'questions': converted_questions}

        with open(output_file, 'w') as f:
            yaml.dump(converted_data, f, default_flow_style=False, sort_keys=False, indent=2)

        return self.conversion_stats

    def validate_yaml_file(self, file_path: str) -> Dict[str, Any]:
        """Validate that a YAML file has proper structure"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'question_count': 0,
            'manifest_count': 0,
            'command_count': 0
        }

        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict) or 'questions' not in data:
                validation_results['valid'] = False
                validation_results['errors'].append("File must contain 'questions' key at root level")
                return validation_results

            validation_results['question_count'] = len(data['questions'])

            for i, question in enumerate(data['questions']):
                q_num = i + 1

                # Check required fields
                if 'question' not in question:
                    validation_results['errors'].append(f"Question {q_num}: Missing 'question' field")

                if 'suggestion' not in question:
                    validation_results['warnings'].append(f"Question {q_num}: Missing 'suggestion' field")
                    continue

                suggestion = question['suggestion']

                # Count types
                if isinstance(suggestion, str) and suggestion.startswith('kubectl'):
                    validation_results['command_count'] += 1
                elif isinstance(suggestion, list):
                    validation_results['manifest_count'] += len(suggestion)

                    # Validate each manifest
                    for j, manifest in enumerate(suggestion):
                        if not isinstance(manifest, dict):
                            validation_results['errors'].append(f"Question {q_num}, suggestion {j+1}: Must be a YAML object")
                        else:
                            if 'apiVersion' not in manifest:
                                validation_results['warnings'].append(f"Question {q_num}, manifest {j+1}: Missing apiVersion")
                            if 'kind' not in manifest:
                                validation_results['warnings'].append(f"Question {q_num}, manifest {j+1}: Missing kind")

        except yaml.YAMLError as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"YAML parsing error: {e}")
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Unexpected error: {e}")

        if validation_results['errors']:
            validation_results['valid'] = False

        return validation_results

def main():
    parser = argparse.ArgumentParser(description='Convert quiz app question formats')
    parser.add_argument('command', choices=['convert', 'validate'], help='Operation to perform')
    parser.add_argument('input_file', help='Input file path')
    parser.add_argument('--output', help='Output file path (for convert command)')
    parser.add_argument('--fix-escaping', action='store_true', help='Attempt to fix escape sequences')

    args = parser.parse_args()

    converter = YAMLConverter()

    if args.command == 'convert':
        if not args.output:
            # Generate output filename
            input_path = Path(args.input_file)
            args.output = str(input_path.with_suffix('.yaml'))

        print(f"Converting {args.input_file} -> {args.output}")

        try:
            stats = converter.convert_questions_file(args.input_file, args.output)

            print("\n=== Conversion Results ===")
            print(f"Total questions: {stats['total_questions']}")
            print(f"Successful conversions: {stats['successful_conversions']}")
            print(f"Already proper format: {stats['already_proper_format']}")
            print(f"Failed conversions: {stats['failed_conversions']}")

            if stats['failed_conversions'] > 0:
                print(f"\n⚠️  {stats['failed_conversions']} questions could not be converted")
                print("   These will remain in their original format")

            print(f"\n✅ Converted file saved as: {args.output}")

        except Exception as e:
            print(f"❌ Conversion failed: {e}")

    elif args.command == 'validate':
        print(f"Validating {args.input_file}...")

        try:
            results = converter.validate_yaml_file(args.input_file)

            print("\n=== Validation Results ===")
            print(f"Status: {'✅ VALID' if results['valid'] else '❌ INVALID'}")
            print(f"Questions: {results['question_count']}")
            print(f"Manifests: {results['manifest_count']}")
            print(f"Commands: {results['command_count']}")

            if results['errors']:
                print(f"\n❌ Errors ({len(results['errors'])}):")
                for error in results['errors']:
                    print(f"  - {error}")

            if results['warnings']:
                print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
                for warning in results['warnings']:
                    print(f"  - {warning}")

            if results['valid'] and not results['warnings']:
                print("\n🎉 File is perfectly formatted!")

        except Exception as e:
            print(f"❌ Validation failed: {e}")

if __name__ == "__main__":
    main()
