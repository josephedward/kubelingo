import pytest
import kubelingo.cli as cli

class DummySelect:
    """Dummy object to simulate an inquirer.select return value."""
    def execute(self):
        return "executed"

def test_select_wrapper_with_kwargs(monkeypatch):
    printed = []
    monkeypatch.setattr(cli.console, 'print', lambda x: printed.append(x))
    # Override the original select to return our dummy
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummySelect())
    choices = ['opt1', 'opt2', 'opt3']
    sel = cli.inquirer.select(message='Choose option:', choices=choices)
    # Ensure wrapper returns the dummy select object
    assert isinstance(sel, DummySelect)
    # Verify printed message and choices exactly once each
    expected = ['[bold]Choose option:[/bold]'] + [f'  {i}) {c}' for i, c in enumerate(choices, start=1)]
    assert printed == expected

def test_select_wrapper_with_positional(monkeypatch):
    printed = []
    monkeypatch.setattr(cli.console, 'print', lambda x: printed.append(x))
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummySelect())
    choices = ['a', 'b']
    # Pass message and choices positionally
    sel = cli.inquirer.select('Pick:', choices)
    assert isinstance(sel, DummySelect)
    expected = ['[bold]Pick:[/bold]', '  1) a', '  2) b']
    assert printed == expected

def test_select_wrapper_empty_choices(monkeypatch):
    printed = []
    monkeypatch.setattr(cli.console, 'print', lambda x: printed.append(x))
    monkeypatch.setattr(cli.inquirer, 'select', lambda message, choices, default=None, style=None: DummySelect())
    sel = cli.inquirer.select(message='Do something', choices=[])
    assert isinstance(sel, DummySelect)
    # Only the message should be printed
    assert printed == ['[bold]Do something[/bold]']
