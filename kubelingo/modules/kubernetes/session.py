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
        """Runs an interactive study session."""
        if not os.getenv("GEMINI_API_KEY"):
            print("\nStudy Mode requires a Gemini API key.")
            print("Set the GEMINI_API_KEY environment variable to enable it.")
            print(
                "You can generate an API key in your Gemini account settings under 'API Keys'."
            )
            return

        if questionary is None:
            print(
                "\nThis feature requires the 'questionary' library for an interactive experience."
            )
            print("Please install it by running: pip install questionary")
            return

        while True:
            try:
                action = questionary.select(
                    "Kubernetes Main Menu",
                    choices=["Study Mode", "Review Questions", "Settings", "Exit"],
                    use_indicator=True,
                ).ask()

                if action is None or action == "Exit":
                    break

                if action == "Study Mode":
                    level = questionary.select(
                        "What is your current overall skill level?",
                        choices=["beginner", "intermediate", "advanced"],
                        default="intermediate",
                    ).ask()
                    if not level:
                        continue

                    study_session = KubernetesStudyMode()
                    study_session.start_study_session(user_level=level)
                elif action in ["Review Questions", "Settings"]:
                    print(f"\nFeature '{action}' is coming soon!")

            except (KeyboardInterrupt, EOFError):
                # The study mode handles its own interrupt messages, so we just exit.
                print("\nReturning to main menu.")
                break
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break

    def cleanup(self):
        """Cleans up any session-related resources."""
        pass


