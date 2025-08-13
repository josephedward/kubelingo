"""
This module is deprecated.

The DBLoader class implemented an old data model where full questions were
loaded from the database. The current architecture uses a metadata-only
database, with YAML files as the single source of truth for question content.
Question loading is now handled by YAMLLoader.
"""
