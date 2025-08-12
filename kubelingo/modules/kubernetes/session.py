import os
import logging

try:
    import questionary
except ImportError:
    questionary = None

from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode, KUBERNETES_TOPICS
from kubelingo.modules.base.session import StudySession


class NewSession(StudySession):
    """A study session for all Kubernetes-related quizzes."""

    def __init__(self, logger):
        """Initializes the session with a logger."""
        super().__init__(logger)

    def initialize(self):
        """Initializes the Kubernetes session."""
        return True

    def run_exercises(self, exercises):
        """Runs an interactive study session using the Socratic method with Gemini."""
        if not os.getenv('GEMINI_API_KEY'):
            print("\nStudy Mode requires a Gemini API key.")
            print("Set the GEMINI_API_KEY environment variable to enable it.")
            print("You can generate an API key in your Gemini account settings under 'API Keys'.")
            return

        if questionary is None:
            print("\nThis feature requires the 'questionary' library for an interactive experience.")
            print("Please install it by running: pip install questionary")
            return

        try:
            topic = questionary.select(
                "Select a topic to study:",
                choices=KUBERNETES_TOPICS,
                use_indicator=True
            ).ask()
            if not topic:
                return

            style = questionary.select(
                "Select a quiz style:",
                choices=[
                    "Open-ended Socratic dialogue",
                    "Basic term/definition recall",
                    "Kubectl command syntax",
                    "YAML manifest authoring",
                ],
                use_indicator=True,
            ).ask()
            if not style:
                return

            if style == "Open-ended Socratic dialogue":
                level = questionary.select(
                    "What is your current skill level on this topic?",
                    choices=["beginner", "intermediate", "advanced"],
                    default="intermediate",
                ).ask()
                if not level:
                    return

                study_session = KubernetesStudyMode()
                response = study_session.start_study_session(topic, level)
                if response is None:
                    print("\nTutor: I'm sorry, I'm having trouble connecting to my knowledge base.")
                    print("This might be due to an invalid API key or a network problem.")
                    print("Please ensure your GEMINI_API_KEY is set correctly and try again.")
                    return

                print(f"\nTutor: {response}")

                while True:
                    user_input = questionary.text("You:").ask()
                    if user_input is None or user_input.lower().strip() in ['exit', 'quit', 'done']:
                        break

                    print("Thinking...")
                    response = study_session.continue_conversation(user_input)
                    if "The study session has not been started" in response:
                        print("\nTutor: " + response)
                        print("Please start a new session.")
                        break

                    print(f"\nTutor: {response}")

                print("\nStudy session ended. Returning to main menu.")

            elif style == "Basic term/definition recall":
                print(f"\nQuiz style '{style}' is not yet implemented. Coming soon!")
                return

            else:
                print(f"\nQuiz style '{style}' is not yet implemented. Coming soon!")
                return

        except (KeyboardInterrupt, EOFError):
            print("\n\nStudy session ended. Returning to main menu.")
        except Exception as e:
            print(f"An error occurred during the study session: {e}")

    def cleanup(self):
        """Cleans up any session-related resources."""
        pass


if __name__ == "__main__":
    session = NewSession(logger=logging.getLogger())
    if session.initialize():
        session.run_exercises(None)
        session.cleanup()
