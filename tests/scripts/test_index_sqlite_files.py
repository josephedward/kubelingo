import sys
from pathlib import Path
import yaml
import pytest

# Add project root to path to allow importing the script from the parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.index_sqlite_files import main as index_sqlite_main


@pytest.fixture
def setup_test_repo(tmp_path: Path):
    """Creates a dummy repo structure with sqlite files for testing."""
    project_root = tmp_path
    (project_root / "dir1").mkdir()
    (project_root / "dir2").mkdir()
    (project_root / "dir2" / "subdir").mkdir()
    (project_root / "backups").mkdir(exist_ok=True)

    # Create dummy sqlite files
    (project_root / "dir1" / "db1.db").touch()
    (project_root / "dir2" / "db2.sqlite").touch()
    (project_root / "dir2" / "subdir" / "db3.sqlite3").touch()
    (project_root / "other.txt").touch()  # A non-db file to be ignored

    return project_root


def test_index_all_sqlite_files(setup_test_repo: Path, monkeypatch):
    """Test indexing all sqlite files in the mock repository."""
    project_root = setup_test_repo

    # Mock the project_root used in the script to point to our temp directory
    monkeypatch.setattr("scripts.index_sqlite_files.project_root", project_root)

    # Mock get_all_sqlite_files_in_repo to return only files from the test repo
    mock_sqlite_files = [
        project_root / "dir1" / "db1.db",
        project_root / "dir2" / "db2.sqlite",
        project_root / "dir2" / "subdir" / "db3.sqlite3",
    ]
    monkeypatch.setattr(
        "scripts.index_sqlite_files.get_all_sqlite_files_in_repo",
        lambda: mock_sqlite_files,
    )

    # Mock sys.argv to run the script with no directory arguments
    monkeypatch.setattr(sys, "argv", ["scripts/index_sqlite_files.py"])

    index_sqlite_main()

    # Verify the index file was created
    index_file = project_root / "backups" / "sqlite_index.yaml"
    assert index_file.exists()

    # Check the content of the index file
    with open(index_file, "r") as f:
        data = yaml.safe_load(f)

    assert "last_updated" in data
    assert len(data["files"]) == 3

    paths = sorted([d["path"] for d in data["files"]])
    expected_paths = sorted([
        "dir1/db1.db",
        "dir2/db2.sqlite",
        "dir2/subdir/db3.sqlite3"
    ])
    assert paths == expected_paths

    for file_info in data["files"]:
        assert file_info["size_bytes"] == 0
        assert "last_modified" in file_info


def test_index_specific_directory(setup_test_repo: Path, monkeypatch):
    """Test indexing a specific directory within the mock repository."""
    project_root = setup_test_repo
    monkeypatch.setattr("scripts.index_sqlite_files.project_root", project_root)

    # Mock sys.argv to run with a specific directory
    target_dir = "dir2"
    monkeypatch.setattr(sys, "argv", ["scripts/index_sqlite_files.py", str(project_root / target_dir)])

    index_sqlite_main()

    index_file = project_root / "backups" / "sqlite_index.yaml"
    assert index_file.exists()

    with open(index_file, "r") as f:
        data = yaml.safe_load(f)

    assert len(data["files"]) == 2
    paths = sorted([d["path"] for d in data["files"]])
    expected_paths = sorted([
        "dir2/db2.sqlite",
        "dir2/subdir/db3.sqlite3"
    ])
    assert paths == expected_paths


def test_no_sqlite_files_found(setup_test_repo: Path, monkeypatch, capsys):
    """Test behavior when no sqlite files are found in the specified directory."""
    project_root = setup_test_repo
    monkeypatch.setattr("scripts.index_sqlite_files.project_root", project_root)

    # Create and target a directory with no sqlite files
    empty_dir = project_root / "empty_dir"
    empty_dir.mkdir()
    monkeypatch.setattr(sys, "argv", ["scripts/index_sqlite_files.py", str(empty_dir)])

    index_sqlite_main()

    # Check for the correct message in stdout
    captured = capsys.readouterr()
    assert "No SQLite files found to index." in captured.out

    # Ensure the index file was not created
    index_file = project_root / "backups" / "sqlite_index.yaml"
    assert not index_file.exists()
