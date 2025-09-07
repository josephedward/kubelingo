import pytest
import cli

@pytest.fixture(scope="module")
def menu_defs():
    return cli.MENU_DEFINITIONS

def test_menu_definitions_have_expected_sections(menu_defs):
    assert 'post_question' in menu_defs, "MENU_DEFINITIONS missing 'post_question' section"
    assert 'post_answer' in menu_defs,   "MENU_DEFINITIONS missing 'post_answer' section"

def test_post_question_header(menu_defs):
    header = menu_defs['post_question'].get('header')
    assert isinstance(header, str), "post_question header should be a string"
    assert header.strip().lower().startswith('post question'), \
        f"Unexpected post_question header: {header}"

def test_post_answer_header(menu_defs):
    header = menu_defs['post_answer'].get('header')
    assert isinstance(header, str), "post_answer header should be a string"
    assert header.strip().lower().startswith('post answer'), \
        f"Unexpected post_answer header: {header}"

def test_post_question_entries_structure(menu_defs):
    entries = menu_defs['post_question'].get('entries')
    expected = [
        ('v', 'vim',       'opens vim for manifest-based questions'),
        ('b', 'backward',  'previous question'),
        ('f', 'forward',   'next question'),
        ('a', 'answer',    'shows solution'),
        ('s', 'visit',     'source (opens browser at source)'),
        ('q', 'quit',      'back to main menu'),
    ]
    assert isinstance(entries, list), "post_question entries should be a list"
    assert entries == expected, \
        f"post_question entries mismatch.\nExpected: {expected}\nFound:    {entries}"

def test_post_answer_entries_structure(menu_defs):
    entries = menu_defs['post_answer'].get('entries')
    expected = [
        ('r', 'retry',   'retry question'),
        ('c', 'correct', 'save as correct'),
        ('m', 'missed',  'save as missed'),
        ('d', 'delete',  'do not save question'),
    ]
    assert isinstance(entries, list), "post_answer entries should be a list"
    assert entries == expected, \
        f"post_answer entries mismatch.\nExpected: {expected}\nFound:    {entries}"