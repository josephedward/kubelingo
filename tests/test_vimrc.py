import os
import re

def test_vimrc_tabs_are_two_spaces():
    # Locate the project root relative to this test file
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    vimrc_path = os.path.join(root, '.vimrc')
    assert os.path.isfile(vimrc_path), ".vimrc file should exist in the project root"

    with open(vimrc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verify Vim settings for spaces instead of tabs and width of two spaces
    assert re.search(r'^\s*set\s+expandtab\s*$', content, re.M), "expandtab must be set"
    assert re.search(r'^\s*set\s+tabstop\s*=\s*2\s*$', content, re.M), "tabstop must be 2"
    assert re.search(r'^\s*set\s+shiftwidth\s*=\s*2\s*$', content, re.M), "shiftwidth must be 2"
    assert re.search(r'^\s*set\s+softtabstop\s*=\s*2\s*$', content, re.M), "softtabstop must be 2"