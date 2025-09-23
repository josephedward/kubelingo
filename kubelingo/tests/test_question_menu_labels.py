import builtins
from io import StringIO
from contextlib import redirect_stdout


def test_pre_answer_menu_labels_for_manifest(monkeypatch):
    from kubelingo import question_manager as qm
    buf = StringIO()
    with redirect_stdout(buf):
        qm.show_question_menu(manifest_capable=True, is_trivia=False)
    out = buf.getvalue()
    assert 'e)dit (vim)' in out
    assert 'n)ext' in out
    assert 'p)revious' in out
    assert 'v)iew answer' in out
    assert 's)ource' in out
    assert 'q)uit' in out


def test_post_answer_menu_labels(monkeypatch):
    from kubelingo import question_manager as qm
    buf = StringIO()
    with redirect_stdout(buf):
        qm.show_post_answer_menu()
    out = buf.getvalue()
    assert 'r) retry' in out
    assert 'c) correct' in out
    assert 'm) missed' in out
    assert 'd) delete question' in out
    # Ensure deprecated items are not present
    assert 'visit' not in out
    assert 'settings' not in out
