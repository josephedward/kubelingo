"""
Stub openai module for environments without the OpenAI SDK.
This allows dynamic imports and patching of ChatCompletion.create in tests.
"""

class ChatCompletion:
    @staticmethod
    def create(*args, **kwargs):
        """Stub method for OpenAI ChatCompletion.create"""
        raise NotImplementedError("openai.ChatCompletion.create is not implemented in stub")