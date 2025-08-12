import os
from kubelingo.modules.kubernetes.study_mode import KubernetesStudyMode, KUBERNETES_TOPICS

class NewSession:
    """A study session for all Kubernetes-related quizzes."""

    def _run_study_mode_session(self):
        """Runs an interactive study session using the Socratic method with Gemini."""
        if not os.getenv('GEMINI_API_KEY'):
            print("\nStudy Mode requires a Gemini API key.")
            print("Set the GEMINI_API_KEY environment variable to enable it.")
            print("You can generate an API key in your Gemini account settings under 'API Keys'.")
            return

        try:
            print()  # Add a blank line for spacing before the menu
            topic_choices = list(KUBERNETES_TOPICS)
            if not topic_choices:
                print("No study topics available for Study Mode.")
                return
            
            topic = input("What Kubernetes topic would you like to study? ")

            if not topic or topic not in topic_choices:
                print("Invalid topic selected.")
                return

            level = input("What is your current skill level on this topic? (beginner/intermediate/advanced): ").strip().lower()
            if level not in ["beginner", "intermediate", "advanced"]:
                level = "intermediate"

            study_session = KubernetesStudyMode()
            response = study_session.start_study_session(topic, level)
            if response is None:
                print("\nTutor: I'm sorry, I'm having trouble connecting to my knowledge base.")
                print("This might be due to an invalid API key or a network problem.")
                print("Please ensure your GEMINI_API_KEY is set correctly and try again.")
                return

            print(f"\nTutor: {response}")

            while True:
                try:
                    user_input = input("\nYou: ")
                    if user_input.lower().strip() in ['exit', 'quit', 'done']:
                        break
                    
                    print("Thinking...")
                    response = study_session.continue_conversation(user_input)
                    if "The study session has not been started" in response:
                        print("\nTutor: " + response)
                        print("Please start a new session.")
                        break

                    print(f"\nTutor: {response}")
                except (KeyboardInterrupt, EOFError):
                    break

            print("\nStudy session ended. Returning to main menu.")

        except Exception as e:
            print(f"An error occurred during the study session: {e}")
