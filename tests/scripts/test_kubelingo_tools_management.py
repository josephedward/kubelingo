import pytest
from pathlib import Path
import sys

def test_dynamic_script_commands_are_correctly_generated(monkeypatch, tmp_path, capsys):
    """
    Tests that the 'run' subcommand correctly generates subcommands for scripts
    in the scripts directory, respecting exclusions.
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create a set of test scripts that should be discovered
    (scripts_dir / "my-script.py").touch()
    (scripts_dir / "another_script.sh").touch()
    (scripts_dir / "script_with_underscores.py").touch()

    # Create scripts that should be excluded by the logic in kubelingo_tools.py
    (scripts_dir / ".hidden.py").touch()
    (scripts_dir / "__init__.py").touch()
    (scripts_dir / "kubelingo_tools.py").touch()
    (scripts_dir / "maintenance_menu.py").touch()
    (scripts_dir / "full_migrate_and_cleanup.py").touch()
    (scripts_dir / "toolbox.py").touch()
    (scripts_dir / "ckad.py").touch()
    (scripts_dir / "generator.py").touch()

    from scripts import kubelingo_tools
    monkeypatch.setattr(kubelingo_tools, 'scripts_dir', scripts_dir)
    # The script loads a shared context file, which won't exist in test context.
    # The script handles this gracefully, but we can also patch repo_root to be safe.
    monkeypatch.setattr(kubelingo_tools, 'repo_root', tmp_path)

    try:
        kubelingo_tools.main(['run', '--help'])
    except SystemExit as e:
        # --help should exit with 0
        assert e.code == 0

    captured = capsys.readouterr()
    stdout = captured.out

    # Check for scripts that should be present as subcommands
    assert "my-script" in stdout
    assert "another-script" in stdout
    assert "script-with-underscores" in stdout

    # Check for scripts that should be excluded
    assert ".hidden" not in stdout
    assert "__init__" not in stdout
    assert "kubelingo-tools" not in stdout
    assert "maintenance-menu" not in stdout
    assert "full-migrate-and-cleanup" not in stdout
    assert "toolbox" not in stdout
    assert "ckad" not in stdout
    assert "generator" not in stdout
