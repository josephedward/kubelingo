import logging

from kubelingo.database import init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def initialize_app():
    """
    Performs necessary startup tasks for the application, primarily database
    schema initialization. Interactive setup is handled by the CLI.
    """
    init_db()


