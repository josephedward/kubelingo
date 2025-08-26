import yaml
import sys
import os
import textwrap

def format_solution_yaml(data):
    # Recursively convert solution strings containing YAML into native mappings/lists
    if isinstance(data, dict):
        for key, value in list(data.items()):
            # Handle single solution entries
            # Convert multi-line YAML solution string into native mapping or list
            if key == 'solution' and isinstance(value, str) and '\n' in value:
                normalized = textwrap.dedent(value).strip()
                try:
                    parsed = yaml.safe_load(normalized)
                    # Replace only if parsed YAML is a mapping or sequence
                    if isinstance(parsed, (dict, list)):
                        data[key] = parsed
                    # otherwise keep the original string
                except yaml.YAMLError as e:
                    print(f"Warning: Could not parse YAML in 'solution'. Keeping original. Error: {e}", file=sys.stderr)
            # Handle multiple solutions entries
            # Handle lists of solutions, converting multi-line YAML strings
            elif key == 'solutions' and isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, str) and '\n' in item:
                        normalized = textwrap.dedent(item).strip()
                        try:
                            parsed = yaml.safe_load(normalized)
                            if isinstance(parsed, (dict, list)):
                                new_list.append(parsed)
                                continue
                        except yaml.YAMLError:
                            pass
                    new_list.append(item)
                data[key] = new_list
                for item in data[key]:
                    format_solution_yaml(item)
            else:
                format_solution_yaml(value)
    elif isinstance(data, list):
        for item in data:
            format_solution_yaml(item)
    return data

if __name__ == "__main__":
    # Accept a single file or a directory of YAML files
    if len(sys.argv) != 2:
        print("Usage: python format_yaml_solution.py <yaml_file_or_directory>", file=sys.stderr)
        sys.exit(1)
    base = sys.argv[1]
    paths = []
    if os.path.isdir(base):
        for root, dirs, files in os.walk(base):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    paths.append(os.path.join(root, fname))
    else:
        if not os.path.exists(base):
            print(f"Error: Path not found: {base}", file=sys.stderr)
            sys.exit(1)
        paths = [base]
    exit_code = 0
    for file_path in paths:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            data = yaml.safe_load(content)
            updated = format_solution_yaml(data)
            updated_content = yaml.safe_dump(updated, indent=2, default_flow_style=False, sort_keys=False)
            with open(file_path, 'w') as f:
                f.write(updated_content)
            print(f"Formatted solutions in {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)
            exit_code = 1
    sys.exit(exit_code)