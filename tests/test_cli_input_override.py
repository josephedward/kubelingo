"""
Test that kubelingo.cli overrides built-in input() to use prompt_toolkit.prompt,
enabling full line editing and history support.
"""
import builtins
import importlib

def test_input_overridden_to_prompt_toolkit():
    # Save original builtins.input
    orig_input = builtins.input
    try:
        # Import CLI module (which performs the override on import)
        import kubelingo.cli as cli
        importlib.reload(cli)
        # PromptToolkit's prompt function should now be builtins.input
        from prompt_toolkit import prompt as pt_prompt
        assert builtins.input is pt_prompt, (
            f"Expected builtins.input to be prompt_toolkit.prompt, got {builtins.input!r}"
        )
    finally:
        # Restore original input to avoid side effects
        builtins.input = orig_input