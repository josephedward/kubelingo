import os
import importlib
import unittest
from unittest.mock import patch

# We are testing the config module, which sets constants on import.
# We must reload it to test different environment variable states.
from kubelingo.utils import config

class TestConfig(unittest.TestCase):

    def test_questions_dir_uses_default_when_env_var_is_unset(self):
        """
        Tests that QUESTIONS_DIR falls back to the default path when the
        KUBELINGO_QUESTIONS_DIR environment variable is not present.
        """
        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(config)
            expected_path = os.path.join(config.PROJECT_ROOT, 'yaml')
            self.assertEqual(config.QUESTIONS_DIR, expected_path)

        # Reload again outside the patch to restore the module to its original state
        # for other tests in the suite.
        importlib.reload(config)

    def test_questions_dir_is_overridden_by_env_var(self):
        """
        Tests that QUESTIONS_DIR is correctly overridden by the
        KUBELINGO_QUESTIONS_DIR environment variable when it is set.
        """
        custom_path = '/tmp/my-custom-questions-for-testing'
        with patch.dict(os.environ, {'KUBELINGO_QUESTIONS_DIR': custom_path}):
            importlib.reload(config)
            self.assertEqual(config.QUESTIONS_DIR, custom_path)

        # Reload again outside the patch to restore the module to its original state.
        importlib.reload(config)
