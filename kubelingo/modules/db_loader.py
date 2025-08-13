from typing import List

from kubelingo.modules.base.loader import BaseLoader
from kubelingo.question import Question


class DBLoader(BaseLoader):
    """
    Discovers and parses question modules from the SQLite database.

    This loader is intentionally disabled. Questions should be loaded from YAML
    files, not the database, which is used for metadata only.
    """

    def discover(self) -> List[str]:
        """
        Returns an empty list, effectively disabling discovery of DB sources.
        """
        return []

    def load_file(self, path: str) -> List[Question]:
        """
        Returns an empty list, effectively disabling loading questions from the DB.

        Args:
            path: The source_file identifier to load questions for.
        """
        return []
