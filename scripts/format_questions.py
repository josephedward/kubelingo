import os
import yaml
import re
import sys
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

def format_yaml_solution_main(base_path):
    paths = []
    if os.path.isdir(base_path):
        for root, dirs, files in os.walk(base_path):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    paths.append(os.path.join(root, fname))
    else:
        if not os.path.exists(base_path):
            print(f"Error: Path not found: {base_path}", file=sys.stderr)
            sys.exit(1)
        paths = [base_path]
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
            print(f"Formatted YAML solutions in {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)
            exit_code = 1
    return exit_code

def convert_text(text):
    # Match single-quoted multi-line manifest solutions
    # Pattern: indent, - 'apiVersion... until closing quote
    pattern = re.compile(
        r"(?P<indent>^[ ]*)- '(?P<content>[\s\S]*?)'", re.MULTILINE
    )
    def repl(m):
        indent = m.group('indent')
        content = m.group('content')
        # Split into lines and remove leading/trailing whitespace
        lines = content.splitlines()
        trimmed = [line.strip() for line in lines if line.strip()]
        # Build block literal
        block = f"{indent}- |-\n"
        for line in trimmed:
            block += f"{indent}  {line}\n"
        return block.rstrip("\n")
    return re.sub(pattern, repl, text)

def process_file_manifest(path):
    try:
        text = open(path, 'r', encoding='utf-8').read()
    except Exception:
        return
    new_text = convert_text(text)
    if new_text != text:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        print(f"Formatted manifest solutions in {path}")

def format_manifest_solutions_main(targets):
    for target in targets:
        for root, _, files in os.walk(target):
            for fname in files:
                if fname.endswith(('.yaml', '.yml')):
                    process_file_manifest(os.path.join(root, fname))

if __name__ == "__main__":
    questions_dir = "/Users/user/Documents/GitHub/kubelingo/questions"

    # Format YAML solutions
    print("\n--- Formatting YAML solutions ---")
    yaml_exit_code = format_yaml_solution_main(questions_dir)
    if yaml_exit_code != 0:
        print("YAML solution formatting completed with errors.")

    # Format manifest solutions
    print("\n--- Formatting manifest solutions ---")
    # The original script used sys.argv[1:] or ['questions'] for targets
    # Here we'll pass the questions_dir directly.
    format_manifest_solutions_main([questions_dir])

    print("\n--- All formatting tasks completed ---")
