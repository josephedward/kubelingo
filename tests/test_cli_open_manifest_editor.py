import os
import pytest
from kubelingo.cli import _open_manifest_editor


def test_open_manifest_editor_returns_template_with_cat(monkeypatch):
    # Simulate using 'cat' as the editor to echo file content
    captured_cmds = []
    monkeypatch.setenv('EDITOR', 'cat')
    monkeypatch.setattr(os, 'system', lambda cmd: captured_cmds.append(cmd) or 0)
    template = 'apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod\n'
    content = _open_manifest_editor(template)
    assert content == template
    assert captured_cmds, "Expected os.system to be called"
    assert captured_cmds[0].startswith('cat '), f"Unexpected editor command: {captured_cmds[0]}"


def test_open_manifest_editor_returns_empty_with_true(monkeypatch):
    # Using 'true' as the editor should result in no change
    monkeypatch.setenv('EDITOR', 'true')
    monkeypatch.setattr(os, 'system', lambda cmd: 0)
    content = _open_manifest_editor()
    assert content == '', "Expected empty content when no template provided"


def test_open_manifest_editor_uses_default_vim_when_no_editor_set(monkeypatch):
    # Remove EDITOR env var to use default 'vim'
    monkeypatch.delenv('EDITOR', raising=False)
    executed = {}
    def fake_system(cmd):
        executed['cmd'] = cmd
        return 0
    monkeypatch.setattr(os, 'system', fake_system)
    template = 'test-content'
    content = _open_manifest_editor(template)
    # Verify default editor 'vim' is used
    assert 'vim ' in executed.get('cmd', ''), f"Expected vim editor, got: {executed.get('cmd')}"
    # Since editor command is no-op, content remains the template
    assert content == template