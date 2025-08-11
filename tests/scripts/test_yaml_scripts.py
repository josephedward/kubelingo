import sqlite3
import sys
import os
import pytest  # noqa: F401
from pathlib import Path
import importlib.util

# Directory containing the maintenance scripts (project root)
ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / 'scripts'

def load_script(name):
    spec = importlib.util.spec_from_file_location(name, str(SCRIPTS_DIR / f'{name}.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    return mod


def test_export_db_to_yaml_and_restore(tmp_path, capsys, monkeypatch):
    # Initialize a fresh test DB and insert a question via the application logic
    db_path = tmp_path / 'db.sqlite'
    import kubelingo.utils.config as config
    # Override database paths to isolate tests
    monkeypatch.setattr(config, 'DATABASE_FILE', str(db_path))
    monkeypatch.setattr(config, 'MASTER_DATABASE_FILE', str(tmp_path / 'no.db'))
    monkeypatch.setattr(config, 'SECONDARY_MASTER_DATABASE_FILE', str(tmp_path / 'no.db'))
    import kubelingo.database as dbmod
    dbmod.init_db(clear=True)
    dbmod.add_question(id='q1', prompt='hello', source_file='f.yaml')
    # Export to YAML
    out_file = tmp_path / 'out.yaml'
    mod_export = load_script('export_db_to_yaml')
    monkeypatch.setattr(sys, 'argv', ['export_db_to_yaml', '-o', str(out_file)])
    mod_export.main()
    exported = out_file.read_text()
    # Load and verify that our question appears in the export
    try:
        import yaml
    except ImportError:
        pytest.skip('PyYAML not installed')
    data = yaml.safe_load(exported)
    assert isinstance(data, list)
    # Should export exactly one question and match our inserted data
    assert len(data) == 1
    item = data[0]
    assert item.get('id') == 'q1'
    assert item.get('prompt') == 'hello'
    assert item.get('source_file') == 'f.yaml'
    # Now restore from YAML
    yaml_input = tmp_path / 'in.yaml'
    yaml.safe_dump(data, open(yaml_input, 'w'))
    # Monkey-patch MASTER paths to avoid seeding
    monkeypatch.setattr(config, 'MASTER_DATABASE_FILE', str(tmp_path / 'no.db'))
    monkeypatch.setattr(config, 'SECONDARY_MASTER_DATABASE_FILE', str(tmp_path / 'no.db'))
    db_file = tmp_path / 'restored.db'
    monkeypatch.setattr(config, 'DATABASE_FILE', str(db_file))
    # Restore directly using the restore function with explicit db_path override
    from pathlib import Path as _Path
    mod_restore = load_script('restore_yaml_to_db')
    # Pass a list of Path objects, clear flag, and override db_path to our test DB
    mod_restore.restore_yaml_to_db([_Path(yaml_input)], clear_db=True, db_path=str(db_file))
    # Verify DB content in the patched DATABASE_FILE
    conn2 = sqlite3.connect(str(db_file))
    cur2 = conn2.cursor()
    cur2.execute('SELECT id, prompt, source_file FROM questions')
    rows = cur2.fetchall()
    conn2.close()
    # Source file equals the input YAML filename
    assert rows == [('q1', 'hello', yaml_input.name)]