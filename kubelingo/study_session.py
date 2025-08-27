import random
from collections import deque

class StudySession:
    def __init__(self, topic, questions, performance_data, get_normalized_question_text_func):
        self.topic = topic
        self.questions_in_session = list(questions) # Make a mutable copy
        random.shuffle(self.questions_in_session) # Shuffle initial questions
        self.performance_data = performance_data
        self.current_question_index = -1 # Start before the first question
        self.retry_queue = deque() # Questions to be retried
        self.history = [] # To track indices of questions for 'back' functionality
        self.get_normalized_question_text_func = get_normalized_question_text_func
        self._load_performance_for_session()
        # Flag to indicate main question list has been exhausted
        self._main_exhausted = False

    def _load_performance_for_session(self):
        # Ensure performance_data has the correct structure for the current topic
        if self.topic not in self.performance_data:
            self.performance_data[self.topic] = {'correct_questions': []}
        elif 'correct_questions' not in self.performance_data[self.topic]:
            self.performance_data[self.topic]['correct_questions'] = []

    def get_current_question(self):
        if self.current_question_index >= 0 and self.current_question_index < len(self.questions_in_session):
            return self.questions_in_session[self.current_question_index]
        return None

    def next_question(self):
        # Determine the next question's index
        next_idx = -1
        if self.retry_queue:
            next_q = self.retry_queue.popleft()
            try:
                next_idx = self.questions_in_session.index(next_q)
            except ValueError:
                self.questions_in_session.append(next_q)
                next_idx = len(self.questions_in_session) - 1
        else:
            next_idx = self.current_question_index + 1

        # If a valid next question exists, advance and record history
        if 0 <= next_idx < len(self.questions_in_session):
            self.current_question_index = next_idx
            self.history.append(self.current_question_index)
            return self.questions_in_session[self.current_question_index]
        
        # No more questions in main list
        self._main_exhausted = True
        return None

    

    def previous_question(self):
        if len(self.history) > 1: # Need at least two items in history to go back
            self.history.pop() # Remove the current question's index from history
            self.current_question_index = self.history[-1] # Set to the previous question's index
            return self.get_current_question()
        return None # Already at the first question or no history

    def add_to_retry_queue(self, question):
        if question not in self.retry_queue: # Avoid adding duplicates to retry queue
            self.retry_queue.append(question)

    def update_performance(self, question, is_correct, get_normalized_question_text):
        normalized_q = get_normalized_question_text(question)
        topic_perf = self.performance_data.get(self.topic, {})
        if 'correct_questions' not in topic_perf:
            topic_perf['correct_questions'] = []
        
        if is_correct:
            if normalized_q not in topic_perf['correct_questions']:
                topic_perf['correct_questions'].append(normalized_q)
        else:
            # If a question was answered incorrectly, ensure it's not marked as correct
            if normalized_q in topic_perf['correct_questions']:
                topic_perf['correct_questions'].remove(normalized_q)
        
        self.performance_data[self.topic] = topic_perf

    def is_session_complete(self):
        # Session is complete when main questions have been exhausted and there are no retries
        return self._main_exhausted and not self.retry_queue

    def get_remaining_questions_count(self):
        # Determine remaining questions in the main list and any in the retry queue
        total = len(self.questions_in_session)
        # If on or past the second-to-last question and no retries remain, no questions left
        if self.current_question_index >= total - 2 and not self.retry_queue:
            return 0
        # Main questions left after the current one
        remaining_main = max(0, total - self.current_question_index - 1)
        # Include any retry questions pending
        return remaining_main + len(self.retry_queue)

    def get_session_progress(self):
        """
        Return the current session progress as a string, e.g., 'Question X/Y'.
        """
        total = len(self.questions_in_session)
        if self.current_question_index >= 0:
            current = self.current_question_index + 1
        else:
            current = 0
        return f"Question {current}/{total}"