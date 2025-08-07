import sys
from unittest.mock import patch

import pytest

from kubelingo.cli import main


pytestmark = pytest.mark.filterwarnings("ignore:Can not control echo on the terminal")


@patch('kubelingo.cli.load_session')
@patch('questionary.select')
def test_yaml_editing_is_in_main_menu(mock_select, mock_load_session):
    """
    Verify that 'YAML Editing' appears in the interactive quiz menu
    and that 'YAML Exercises' is not present.
    """
    # Mock the return value of questionary to 'Exit' to prevent the app
    # from trying to run a quiz and to ensure a clean exit.
    mock_select.return_value.ask.return_value = 'Exit'

    # The main quiz menu is currently invoked via the --k8s flag
    sys.argv = ['kubelingo', '--k8s']

    try:
        main()
    except SystemExit:
        # main() is expected to call sys.exit(), which raises SystemExit
        pass

    # Ensure that questionary.select was called to display the menu
    mock_select.assert_called_once()

    # Extract the choices passed to questionary.select
    call_kwargs = mock_select.call_args.kwargs
    choices = call_kwargs.get('choices', [])

    # The choices can be complex objects, so extract their names for assertion
    choice_names = []
    for choice in choices:
        if isinstance(choice, str):
            choice_names.append(choice)
        elif isinstance(choice, dict) and 'name' in choice:
            choice_names.append(choice['name'])

    assert "YAML Editing" in choice_names
    assert "YAML Exercises" not in choice_names
    assert "Exit" in choice_names
