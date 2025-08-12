# Core Concepts for Kubelingo

This document outlines fundamental concepts that should be known by all agents working on the Kubelingo codebase.

## Exercise Categories vs. Subject Matter

The Kubelingo question system has a two-level hierarchy for classifying questions:

1.  **Exercise Categories**: These are three broad, fixed categories that define the *modality* or *type* of the question. They are fundamental to the application's structure.
    *   `basic`: For open-ended, conceptual questions (Socratic method).
    *   `command`: For quizzes on specific single-line commands (e.g., `kubectl`, `vim`).
    *   `manifest`: For exercises involving authoring or editing Kubernetes YAML files.

2.  **Subject Matter**: These are more specific, flexible topics that describe the *content* of the question. They are numerous and can be easily added or changed to allow for experimentation and new content areas.
    *   Examples include: "Core Concepts", "Pod Design", "Security", "Networking", etc.

### Mapping in the Code

-   In the database (`questions` table), the **Exercise Category** is stored in the `category_id` column.
-   The **Subject Matter** is stored in the `subject_id` column.
-   In the source YAML files, the **Subject Matter** is specified using the `category` key. The **Exercise Category** is determined from the `type` key (e.g., `type: socratic` maps to the `basic` category).
