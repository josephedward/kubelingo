import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner


def test_create_lab_mock_non_interactive(tmp_path: Path):
    # Arrange
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True, exist_ok=True)

    from kubelingo.create_lab import main as create_lab_cli

    runner = CliRunner()
    result = runner.invoke(
        create_lab_cli,
        [
            "--root",
            str(out_root),
            "--lab-category",
            "ckad",
            "--lab-id",
            "003",
            "--topic",
            "deployment",
            "--difficulty",
            "medium",
            "--mock",
            "--non-interactive",
        ],
    )

    # Assert CLI ran successfully
    assert result.exit_code == 0, result.output

    # Verify structure and files
    base = out_root / "facilitator" / "assets" / "exams" / "ckad" / "003"
    assert (base / "config.json").exists()
    assert (base / "assessment.json").exists()
    assert (base / "answers.md").exists()
    # Registry updated
    reg = out_root / "facilitator" / "assets" / "exams" / "labs.json"
    assert reg.exists()
    import json as _json
    with open(reg, 'r') as f:
        labs = _json.load(f)
    ids = [l.get('id') for l in labs.get('labs', [])]
    assert f"ckad-003" in ids

    # Scripts directories (may be nested under scripts/<qid>/{setup,validation})
    scripts_dir = base / "scripts"
    assert scripts_dir.exists()
    # Find a validation script anywhere under scripts
    validation_candidates = list(scripts_dir.rglob("*_validate.sh"))
    assert validation_candidates, "Expected a validation script to be generated"

    # Assessment content references the validation script file name
    with open(base / "assessment.json", "r") as f:
        data = json.load(f)
    assert "questions" in data and isinstance(data["questions"], list)
    assert data["questions"], "Assessment should have at least one question"
    ver = data["questions"][0].get("verification", [])
    assert ver, "Verification steps should exist"
    # The script filename should be present under scripts/validation
    val_file = ver[0]["verificationScriptFile"]
    # Confirm referenced relative file exists under scripts
    assert (scripts_dir / val_file).exists()
