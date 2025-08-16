import unittest
from unittest.mock import patch
import io
import sys
import os

# Add project root to path to allow importing kubelingo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from kubelingo import get_user_input

class TestGetUserInput(unittest.TestCase):

    @patch('builtins.input', side_effect=['cmd1', 'back', 'done'])
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_back_command_removes_last_entry(self, mock_stdout, mock_input):
        """Tests that 'back' removes the previously entered command."""
        user_commands, special_action = get_user_input()
        self.assertEqual(user_commands, [])
        self.assertIsNone(special_action)
        self.assertIn("(Removed: 'cmd1')", mock_stdout.getvalue())

    @patch('builtins.input', side_effect=['back', 'done'])
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_back_command_on_empty_list(self, mock_stdout, mock_input):
        """Tests that 'back' does nothing when the command list is empty."""
        user_commands, special_action = get_user_input()
        self.assertEqual(user_commands, [])
        self.assertIsNone(special_action)
        self.assertIn("(No lines to remove)", mock_stdout.getvalue())

    @patch('builtins.input', side_effect=['cmd1', 'cmd2', 'back', 'cmd3', 'done'])
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_back_command_in_the_middle(self, mock_stdout, mock_input):
        """Tests using 'back' to remove a command between other commands."""
        user_commands, special_action = get_user_input()
        self.assertEqual(user_commands, ['cmd1', 'cmd3'])
        self.assertIsNone(special_action)
        self.assertIn("(Removed: 'cmd2')", mock_stdout.getvalue())
