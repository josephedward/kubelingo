import pytest
import kubelingo.question_search as qs

def test_filter_files_returns_only_matching_md_and_prefix():
    tree_data = {
        'tree': [
            {'path': 'prefix/file1.md', 'type': 'blob'},
            {'path': 'prefix/file2.txt', 'type': 'blob'},
            {'path': 'other/file3.md', 'type': 'blob'},
            {'path': 'prefix/file4.md', 'type': 'blob'}
        ]
    }
    result = qs.filter_files(tree_data, ('.md',), path_prefix='prefix/')
    paths = [item['path'] for item in result]
    assert 'prefix/file1.md' in paths
    assert 'prefix/file4.md' in paths
    assert all(p.startswith('prefix/') for p in paths)
    assert 'prefix/file2.txt' not in paths
    assert 'other/file3.md' not in paths

def test_extract_questions_and_answers_from_readme_extracts_pairs_correctly():
    content = '''
Intro text
What is foo show
```bash
foo-answer
```
Some other text
Next question show
```bash
next-answer
```
End'''
    qa = qs.extract_questions_and_answers_from_readme(content)
    assert isinstance(qa, list)
    assert qa == [
        {'question': 'What is foo', 'suggestion': ['foo-answer']},
        {'question': 'Next question', 'suggestion': ['next-answer']}
    ]

def test_validate_kubernetes_manifest_accepts_valid_and_rejects_invalid():
    valid = '''apiVersion: v1
kind: Pod
metadata:
  name: test'''
    assert qs.validate_kubernetes_manifest(valid)
    missing_kind = '''apiVersion: v1
metadata:
  name: test'''
    assert not qs.validate_kubernetes_manifest(missing_kind)
    not_yaml = 'not a yaml'
    assert not qs.validate_kubernetes_manifest(not_yaml)

def test_search_for_questions_uses_repo_tree_and_fetch(monkeypatch):
    # Prepare fake tree with a .md under mapped prefix
    fake_tree = {'tree': [
        {'path': '1.Core_Concepts/foo.md', 'type': 'blob'},
        {'path': '1.Core_Concepts/bar.txt', 'type': 'blob'}
    ]}
    monkeypatch.setattr(qs, 'get_repo_tree', lambda owner, repo, branch='main': fake_tree)
    # Provide fake markdown content for foo.md
    sample_md = 'Sample question show\n```bash\nsample-answer\n```'
    monkeypatch.setattr(qs, 'fetch_file_content', lambda url: sample_md)
    # Topic mapped to '1.Core_Concepts'
    results = qs.search_for_questions('api_discovery_docs')
    assert isinstance(results, list)
    # Should find at least one question matching the sample
    expected = {'question': 'Sample question', 'suggestion': ['sample-answer']}
    assert expected in results
    # If repo tree fetch fails, returns empty list
    monkeypatch.setattr(qs, 'get_repo_tree', lambda owner, repo, branch='main': None)
    assert qs.search_for_questions('api_discovery_docs') == []