"""
Kubernetes study session implementation.
Handles live Kubernetes exercises using gosandbox/eksctl and logs results.
"""
import os
import logging
from kubelingo.modules.base.session import StudySession
from kubelingo.modules.k8s_quiz import commands_equivalent
from kubelingo.cli import load_questions, handle_live_k8s_question, Fore, Style

class KubernetesSession(StudySession):
    """
    Implements StudySession for Kubernetes cloud-based quizzes.
    """
    def __init__(self, questions_file, exercises_file=None, cluster_context=None):
        self.questions_file = questions_file
        self.exercises_file = exercises_file
        self.cluster_context = cluster_context
        self.logger = None

    def initialize(self):
        """Set up logging and cluster context."""
        log_file = 'quiz_cloud_log.txt'
        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
        self.logger = logging.getLogger('kubelingo.kubernetes')
        if self.cluster_context:
            os.environ['KUBECTL_CONTEXT'] = self.cluster_context

    def run_exercises(self):
        """Load questions and run live Kubernetes exercises."""
        questions = load_questions(self.questions_file)
        cloud_qs = [q for q in questions if q.get('type') == 'live_k8s_edit']
        if not cloud_qs:
            print("No live Kubernetes cloud exercises found in data file.")
            return
        total = len(cloud_qs)
        for idx, q in enumerate(cloud_qs, start=1):
            print(f"\n{Fore.CYAN}=== Kubernetes Exercise {idx}/{total} ==={Style.RESET_ALL}")
            is_correct, _ = handle_live_k8s_question(q, self.logger)
            if q.get('explanation'):
                level = Fore.GREEN if is_correct else Fore.RED
                print(level + f"Explanation: {q['explanation']}" + Style.RESET_ALL + '\n')

    def cleanup(self):
        """Cleanup environment variables and resources."""
        if 'KUBECTL_CONTEXT' in os.environ:
            del os.environ['KUBECTL_CONTEXT']