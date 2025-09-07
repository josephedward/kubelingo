import os
import json
import pytest
import kubelingo.cli as cli
from InquirerPy import inquirer

@pytest.fixture(autouse=True)
def use_tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield
