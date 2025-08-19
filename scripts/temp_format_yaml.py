import re
import os

file_path = "/Users/user/Documents/GitHub/kubelingo/questions/services.yaml"

with open(file_path, 'r') as f:
    content = f.read()

def replace_solution(match):
    current_indent = match.group(1)
    solution_content_escaped = match.group(2)

    solution_content_unescaped = solution_content_escaped.replace('''\n''', '''
''')

    content_block_indent = current_indent + '''  '''

    indented_lines = []
    for line in solution_content_unescaped.split('''
'''):
        indented_lines.append(content_block_indent + line)

    new_solution_block = f"{current_indent}solution: |\n" + "\n".join(indented_lines)
    return new_solution_block

modified_content = re.sub(r'''(\s*solution: ")([^"]*)(")''', replace_solution, content)

print(modified_content)
